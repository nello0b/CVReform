from pathlib import Path

import pikepdf
import pytest
from PIL import Image

from app.services.pdf_page_renderer import PDFPageRenderingError, render_pdf_pages


def test_render_pdf_pages_creates_ordered_rgb_pngs(tmp_path: Path) -> None:
    source = tmp_path / "resume.pdf"
    with pikepdf.Pdf.new() as pdf:
        pdf.add_blank_page(page_size=(595, 842))
        pdf.add_blank_page(page_size=(595, 842))
        pdf.save(source)

    output = tmp_path / "pages"
    result = render_pdf_pages(source, output, dpi=150)

    assert [page.page_number for page in result.pages] == [1, 2]
    assert [page.filename for page in result.pages] == ["page-001.png", "page-002.png"]
    assert result.output_directory == output.resolve()
    for rendered_page in result.pages:
        image_path = output / rendered_page.filename
        with Image.open(image_path) as image:
            assert image.format == "PNG"
            assert image.mode == "RGB"
            assert image.width == rendered_page.width
            assert image.height == rendered_page.height
            assert image.width > 1_000
            assert image.height > 1_700
        assert rendered_page.media_type == "image/png"
        assert rendered_page.size == image_path.stat().st_size
        assert rendered_page.dpi == 150


def test_render_pdf_pages_rejects_invalid_pdf(tmp_path: Path) -> None:
    source = tmp_path / "broken.pdf"
    source.write_bytes(b"not a pdf")

    with pytest.raises(PDFPageRenderingError, match="could not be rendered"):
        render_pdf_pages(source, tmp_path / "pages")
