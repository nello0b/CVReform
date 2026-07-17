"""Render complete PDF pages into deterministic visual-reference images."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pymupdf

MAX_PDF_PAGES = 20
MAX_PAGE_PIXELS = 20_000_000


class PDFPageRenderingError(RuntimeError):
    """Raised when a PDF cannot be safely rendered into page images."""


@dataclass(frozen=True)
class RenderedPDFPage:
    """Metadata for one full-page PNG visual reference."""

    page_number: int
    filename: str
    media_type: str
    width: int
    height: int
    size: int
    dpi: int


@dataclass(frozen=True)
class PDFPageRenderingResult:
    """The ordered page images rendered from one PDF."""

    pages: tuple[RenderedPDFPage, ...]
    output_directory: Path


def render_pdf_pages(
    source: Path,
    output_directory: Path,
    *,
    dpi: int = 150,
) -> PDFPageRenderingResult:
    """Render every PDF page to an ordered RGB PNG at the requested DPI."""

    source = source.resolve()
    output_directory = output_directory.resolve()
    if not source.is_file():
        raise PDFPageRenderingError(f"PDF source file does not exist: {source}")
    if source.suffix.lower() != ".pdf":
        raise PDFPageRenderingError("Page rendering accepts PDF files only.")
    if not 72 <= dpi <= 300:
        raise PDFPageRenderingError("Page rendering DPI must be between 72 and 300.")

    output_directory.mkdir(parents=True, exist_ok=True)
    rendered_pages: list[RenderedPDFPage] = []

    try:
        with pymupdf.open(source) as document:
            if document.page_count == 0:
                raise PDFPageRenderingError("The PDF contains no pages.")
            if document.page_count > MAX_PDF_PAGES:
                raise PDFPageRenderingError(
                    f"The PDF exceeds the {MAX_PDF_PAGES}-page rendering limit."
                )

            for page_index, page in enumerate(document):
                expected_width = math.ceil(page.rect.width * dpi / 72)
                expected_height = math.ceil(page.rect.height * dpi / 72)
                if expected_width * expected_height > MAX_PAGE_PIXELS:
                    raise PDFPageRenderingError(
                        f"PDF page {page_index + 1} is too large to render safely."
                    )

                pixmap = page.get_pixmap(
                    dpi=dpi,
                    colorspace=pymupdf.csRGB,
                    alpha=False,
                )
                filename = f"page-{page_index + 1:03d}.png"
                destination = output_directory / filename
                pixmap.save(destination)
                rendered_pages.append(
                    RenderedPDFPage(
                        page_number=page_index + 1,
                        filename=filename,
                        media_type="image/png",
                        width=pixmap.width,
                        height=pixmap.height,
                        size=destination.stat().st_size,
                        dpi=dpi,
                    )
                )
    except PDFPageRenderingError:
        raise
    except (pymupdf.FileDataError, OSError, RuntimeError, ValueError) as error:
        raise PDFPageRenderingError("The PDF could not be rendered into page images.") from error

    return PDFPageRenderingResult(
        pages=tuple(rendered_pages),
        output_directory=output_directory,
    )
