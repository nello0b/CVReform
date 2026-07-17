from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from app.schemas.cv_html import CVHTMLResult
from app.services import cv_processing
from app.services.cv_processing import CVProcessingService
from app.services.document_asset_extractor import (
    AssetExtractionResult,
    ExtractedAsset,
)
from app.services.document_link_extractor import ExtractedLink
from app.services.pdf_page_renderer import PDFPageRenderingResult, RenderedPDFPage


@pytest.mark.anyio
async def test_process_extracts_assets_reconstructs_and_saves_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "resume.docx"
    pdf = tmp_path / "resume.pdf"
    source.write_bytes(b"docx")
    pdf.write_bytes(b"%PDF-test")
    output = tmp_path / "processed"
    asset = ExtractedAsset(
        asset_id="asset-001",
        filename="asset-001.png",
        media_type="image/png",
        width=100,
        height=80,
        size=7,
        sha256="digest",
        pages=(),
        source_names=("image1.png",),
    )
    extraction = AssetExtractionResult(assets=(asset,), warnings=("asset warning",))
    page_image = RenderedPDFPage(
        page_number=1,
        filename="page-001.png",
        media_type="image/png",
        width=1240,
        height=1754,
        size=8,
        dpi=150,
    )
    link = ExtractedLink(
        link_id="link-001",
        destination="https://github.com/example",
        pages=(),
        source_names=("document.xml.rels",),
    )

    def fake_extract(source_document: Path, assets_directory: Path) -> AssetExtractionResult:
        assert source_document == source
        assets_directory.mkdir(parents=True)
        (assets_directory / asset.filename).write_bytes(b"pngdata")
        return extraction

    monkeypatch.setattr(cv_processing, "extract_document_assets", fake_extract)
    monkeypatch.setattr(cv_processing, "extract_document_links", lambda _: (link,))

    def fake_render(pdf_document: Path, page_directory: Path, *, dpi: int):
        assert pdf_document == pdf
        assert dpi == 150
        page_directory.mkdir(parents=True)
        (page_directory / page_image.filename).write_bytes(b"page-png")
        return PDFPageRenderingResult(
            pages=(page_image,),
            output_directory=page_directory,
        )

    monkeypatch.setattr(cv_processing, "render_pdf_pages", fake_render)
    document = CVHTMLResult(
        html='<article class="cv-document"></article>',
        css=".cv-document { color: black; }",
        warnings=["AI warning"],
    )
    reconstruction = SimpleNamespace(reconstruct_pdf=AsyncMock(return_value=document))
    settings = Settings(
        _env_file=None,
        CVREFORM_SEND_PAGE_IMAGES=True,
        CVREFORM_PAGE_IMAGE_DPI=150,
    )
    service = CVProcessingService(
        reconstruction_service=reconstruction,
        settings=settings,
    )

    result = await service.process(
        source_document=source,
        pdf_document=pdf,
        output_directory=output,
        asset_url_prefix="/api/v1/cvs/test/assets",
    )

    reconstruction.reconstruct_pdf.assert_awaited_once_with(
        pdf,
        assets=(asset,),
        assets_directory=output / "assets",
        asset_url_prefix="/api/v1/cvs/test/assets",
        links=(link,),
        page_images=(page_image,),
        page_images_directory=output / "page-images",
    )
    assert (output / "document.html").read_text(encoding="utf-8") == document.html
    assert (output / "styles.css").read_text(encoding="utf-8") == document.css
    assert result.document.warnings == ["asset warning", "AI warning"]
    assert result.links == (link,)
    assert result.page_rendering is not None
    assert result.page_rendering.pages == (page_image,)
