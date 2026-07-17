import os
from pathlib import Path

import pytest

from app.services.document_asset_extractor import extract_document_assets

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANUAL_FIXTURES_DIRECTORY = PROJECT_ROOT / "tests" / "fixtures" / "manual"
MANUAL_TEST_ENABLED = os.getenv("CVREFORM_RUN_MANUAL_ASSET_TESTS", "").lower() in {
    "1",
    "true",
    "yes",
    "on",
}


@pytest.mark.manual
@pytest.mark.skipif(
    not MANUAL_TEST_ENABLED,
    reason="Set CVREFORM_RUN_MANUAL_ASSET_TESTS=1 to test private local documents.",
)
@pytest.mark.parametrize(
    "filename",
    ["with-image1.pdf", "with-image2.docx", "with-image3.pdf"],
)
def test_prepared_documents_extract_images(filename: str) -> None:
    source = MANUAL_FIXTURES_DIRECTORY / filename
    if not source.is_file():
        pytest.fail(f"Manual test document is missing: {source}")

    output_directory = PROJECT_ROOT / "storage" / "test-assets" / source.stem
    output_directory.mkdir(parents=True, exist_ok=True)

    # Remove only assets produced by an earlier run of this same manual test.
    for old_asset in output_directory.glob("asset-*.*"):
        old_asset.unlink()

    result = extract_document_assets(source, output_directory)

    assert result.assets, f"No extractable raster images were found in {filename}."
    for asset in result.assets:
        assert (output_directory / asset.filename).is_file()

    print(f"\n{filename}: extracted {len(result.assets)} unique image(s)")
    print(f"Output: {output_directory}")
    for asset in result.assets:
        print(
            f"- {asset.asset_id}: {asset.filename}, {asset.width}x{asset.height}, "
            f"pages={asset.pages or 'DOCX package'}"
        )
    for warning in result.warnings:
        print(f"Warning: {warning}")
