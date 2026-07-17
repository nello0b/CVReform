"""Extract verified external hyperlink destinations from PDF and DOCX files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

import pikepdf

ALLOWED_LINK_SCHEMES = {"http", "https", "mailto", "tel"}
RELATIONSHIP_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
HYPERLINK_RELATIONSHIP = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
)


class LinkExtractionError(RuntimeError):
    """Raised when a source document cannot be inspected for hyperlinks."""


@dataclass(frozen=True)
class ExtractedLink:
    link_id: str
    destination: str
    pages: tuple[int, ...]
    source_names: tuple[str, ...]


def extract_document_links(source: Path) -> tuple[ExtractedLink, ...]:
    """Extract safe external destinations from one PDF or DOCX document."""

    extension = source.suffix.lower()
    if extension == ".pdf":
        links = _extract_pdf_link_data(source)
    elif extension == ".docx":
        links = _extract_docx_link_data(source)
    else:
        raise LinkExtractionError("Link extraction supports only PDF and DOCX documents.")

    return tuple(
        ExtractedLink(
            link_id=f"link-{index:03d}",
            destination=destination,
            pages=tuple(sorted(data["pages"])),
            source_names=tuple(sorted(data["source_names"])),
        )
        for index, (destination, data) in enumerate(links.items(), start=1)
    )


def _extract_pdf_link_data(source: Path) -> dict[str, dict[str, set]]:
    source = source.resolve()
    if not source.is_file():
        raise LinkExtractionError(f"PDF source file does not exist: {source}")

    links: dict[str, dict[str, set]] = {}
    try:
        with pikepdf.Pdf.open(source) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                for annotation in page.obj.get("/Annots", []):
                    if str(annotation.get("/Subtype", "")) != "/Link":
                        continue
                    action = annotation.get("/A")
                    if action is None or str(action.get("/S", "")) != "/URI":
                        continue
                    destination = str(action.get("/URI", "")).strip()
                    if _is_safe_destination(destination):
                        data = links.setdefault(
                            destination,
                            {"pages": set(), "source_names": set()},
                        )
                        data["pages"].add(page_number)
                        data["source_names"].add("PDF link annotation")
    except (pikepdf.PdfError, OSError, ValueError) as error:
        raise LinkExtractionError(f"The PDF links could not be inspected: {error}") from error
    return links


def _extract_docx_link_data(source: Path) -> dict[str, dict[str, set]]:
    source = source.resolve()
    if not source.is_file():
        raise LinkExtractionError(f"DOCX source file does not exist: {source}")

    links: dict[str, dict[str, set]] = {}
    try:
        with ZipFile(source) as archive:
            relationship_files = [
                name
                for name in archive.namelist()
                if name.startswith("word/_rels/") and name.endswith(".rels")
            ]
            for relationship_file in relationship_files:
                root = ElementTree.fromstring(archive.read(relationship_file))
                for relationship in root.findall(
                    f"{{{RELATIONSHIP_NAMESPACE}}}Relationship"
                ):
                    if relationship.get("Type") != HYPERLINK_RELATIONSHIP:
                        continue
                    destination = (relationship.get("Target") or "").strip()
                    if _is_safe_destination(destination):
                        data = links.setdefault(
                            destination,
                            {"pages": set(), "source_names": set()},
                        )
                        data["source_names"].add(relationship_file)
    except (BadZipFile, ElementTree.ParseError, KeyError, OSError) as error:
        raise LinkExtractionError(f"The DOCX links could not be inspected: {error}") from error
    return links


def _is_safe_destination(destination: str) -> bool:
    return urlsplit(destination).scheme.lower() in ALLOWED_LINK_SCHEMES
