from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image

from app.services.document_asset_extractor import (
    AssetExtractionError,
    extract_document_assets,
    extract_docx_assets,
    extract_pdf_assets,
)


def _png_bytes(color: str = "red") -> bytes:
    output = BytesIO()
    Image.new("RGB", (20, 10), color=color).save(output, format="PNG")
    return output.getvalue()


def test_extract_docx_assets_saves_and_deduplicates_images(tmp_path: Path) -> None:
    source = tmp_path / "example.docx"
    image = _png_bytes()
    with ZipFile(source, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
        archive.writestr("word/media/profile.png", image)
        archive.writestr("word/media/profile-copy.png", image)

    result = extract_docx_assets(source, tmp_path / "assets")

    assert len(result.assets) == 1
    asset = result.assets[0]
    assert asset.asset_id == "asset-001"
    assert asset.media_type == "image/png"
    assert (asset.width, asset.height) == (20, 10)
    assert asset.source_names == ("profile-copy.png", "profile.png")
    assert (tmp_path / "assets" / asset.filename).read_bytes() == image
    assert result.warnings == ()


def test_extract_pdf_assets_records_the_source_page(tmp_path: Path) -> None:
    source = tmp_path / "example.pdf"
    Image.new("RGB", (20, 10), color="blue").save(source, format="PDF")

    result = extract_pdf_assets(source, tmp_path / "assets")

    assert len(result.assets) == 1
    assert result.assets[0].pages == (1,)
    assert result.assets[0].media_type in {"image/jpeg", "image/png"}
    assert (tmp_path / "assets" / result.assets[0].filename).is_file()


def test_docx_extraction_skips_invalid_media_without_failing(tmp_path: Path) -> None:
    source = tmp_path / "example.docx"
    with ZipFile(source, "w") as archive:
        archive.writestr("word/media/broken.png", b"not an image")

    result = extract_docx_assets(source, tmp_path / "assets")

    assert result.assets == ()
    assert len(result.warnings) == 1
    assert "broken.png" in result.warnings[0]


def test_document_asset_extraction_dispatches_and_rejects_unknown_types(
    tmp_path: Path,
) -> None:
    source = tmp_path / "example.txt"
    source.write_text("example", encoding="utf-8")

    with pytest.raises(AssetExtractionError, match="only PDF and DOCX"):
        extract_document_assets(source, tmp_path / "assets")
