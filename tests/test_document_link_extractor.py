from pathlib import Path
from zipfile import ZipFile

import pikepdf

from app.services.document_link_extractor import extract_document_links


def test_extract_docx_links_keeps_safe_external_destinations(tmp_path: Path) -> None:
    source = tmp_path / "resume.docx"
    relationships = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
    Target="https://github.com/example" TargetMode="External" />
  <Relationship Id="rId2"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
    Target="javascript:alert(1)" TargetMode="External" />
</Relationships>"""
    with ZipFile(source, "w") as archive:
        archive.writestr("word/_rels/document.xml.rels", relationships)

    links = extract_document_links(source)

    assert len(links) == 1
    assert links[0].link_id == "link-001"
    assert links[0].destination == "https://github.com/example"


def test_extract_pdf_links_reads_uri_annotations(tmp_path: Path) -> None:
    source = tmp_path / "resume.pdf"
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page()
    annotation = pikepdf.Dictionary(
        Type=pikepdf.Name.Annot,
        Subtype=pikepdf.Name.Link,
        Rect=pikepdf.Array([0, 0, 100, 20]),
        A=pikepdf.Dictionary(
            S=pikepdf.Name.URI,
            URI=pikepdf.String("https://www.linkedin.com/in/example"),
        ),
    )
    page.obj.Annots = pikepdf.Array([pdf.make_indirect(annotation)])
    pdf.save(source)

    links = extract_document_links(source)

    assert len(links) == 1
    assert links[0].destination == "https://www.linkedin.com/in/example"
    assert links[0].pages == (1,)
