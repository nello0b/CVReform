from io import BytesIO
from pathlib import Path
from shutil import rmtree
from unittest.mock import AsyncMock
from uuid import uuid4
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import uploads
from app.schemas.cv_html import CVHTMLResult
from app.services.cv_processing import CVProcessingResult, get_cv_processing_service
from app.services.document_asset_extractor import (
    AssetExtractionResult,
    ExtractedAsset,
)
from app.services.document_converter import (
    DocumentConversionError,
    DocumentConverterNotFoundError,
)
from app.services.document_link_extractor import ExtractedLink

client = TestClient(app)


@pytest.fixture(autouse=True)
def use_temporary_upload_directory(monkeypatch):
    test_directory = Path("storage/test-uploads") / uuid4().hex
    processed_directory = test_directory / "processed"
    monkeypatch.setattr(uploads, "UPLOAD_DIRECTORY", test_directory)
    monkeypatch.setattr(uploads, "PROCESSED_DIRECTORY", processed_directory)
    for setting_name in (
        "CVREFORM_ACCEPT_DOCX",
        "CVREFORM_ACCEPT_PDF",
        "CVREFORM_CONVERT_DOCX_TO_PDF",
    ):
        monkeypatch.delenv(setting_name, raising=False)
    yield
    app.dependency_overrides.clear()
    rmtree(test_directory, ignore_errors=True)


def make_docx() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
    return output.getvalue()


def test_upload_docx() -> None:
    content = make_docx()

    response = client.post(
        "/api/v1/cvs/upload",
        files={
            "file": (
                "resume.docx",
                content,
                uploads.DOCX_CONTENT_TYPE,
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "resume.docx"
    assert body["content_type"] == uploads.DOCX_CONTENT_TYPE
    assert body["size"] == len(content)
    assert body["stored_filename"] == f"{body['upload_id']}.docx"
    assert body["pdf_filename"] is None
    assert (uploads.UPLOAD_DIRECTORY / body["stored_filename"]).read_bytes() == content


def test_capabilities_follow_independent_feature_flags(monkeypatch) -> None:
    defaults = client.get("/api/v1/cvs/capabilities")
    assert defaults.json() == {
        "accept_docx": True,
        "accept_pdf": False,
        "convert_docx_to_pdf": False,
        "accepted_extensions": [".docx"],
    }

    monkeypatch.setenv("CVREFORM_ACCEPT_DOCX", "false")
    monkeypatch.setenv("CVREFORM_ACCEPT_PDF", "true")
    monkeypatch.setenv("CVREFORM_CONVERT_DOCX_TO_PDF", "true")
    pdf_only = client.get("/api/v1/cvs/capabilities")
    assert pdf_only.json() == {
        "accept_docx": False,
        "accept_pdf": True,
        "convert_docx_to_pdf": False,
        "accepted_extensions": [".pdf"],
    }


def test_upload_pdf_when_pdf_support_is_enabled(monkeypatch) -> None:
    monkeypatch.setenv("CVREFORM_ACCEPT_PDF", "true")
    content = b"%PDF-1.7\nCV content"

    response = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("resume.pdf", content, uploads.PDF_CONTENT_TYPE)},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["stored_filename"] == f"{body['upload_id']}.pdf"
    assert body["pdf_filename"] == body["stored_filename"]
    assert (uploads.UPLOAD_DIRECTORY / body["stored_filename"]).read_bytes() == content


def test_convert_docx_to_pdf_when_pdf_support_is_enabled(monkeypatch) -> None:
    monkeypatch.setenv("CVREFORM_CONVERT_DOCX_TO_PDF", "true")

    def fake_conversion(source: Path, output: Path) -> Path:
        assert source.suffix == ".docx"
        output.write_bytes(b"%PDF-1.7\nconverted")
        return output

    monkeypatch.setattr(uploads, "convert_docx_to_pdf", fake_conversion)

    response = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("resume.docx", make_docx(), uploads.DOCX_CONTENT_TYPE)},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["pdf_filename"] == f"{body['upload_id']}.pdf"
    assert (uploads.UPLOAD_DIRECTORY / body["pdf_filename"]).read_bytes().startswith(b"%PDF-")


def test_conversion_failure_removes_partial_upload(monkeypatch) -> None:
    monkeypatch.setenv("CVREFORM_CONVERT_DOCX_TO_PDF", "true")

    def fail_conversion(source: Path, output: Path) -> Path:
        output.write_bytes(b"partial")
        raise DocumentConversionError("conversion failed")

    monkeypatch.setattr(uploads, "convert_docx_to_pdf", fail_conversion)

    response = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("resume.docx", make_docx(), uploads.DOCX_CONTENT_TYPE)},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "The DOCX file could not be converted to PDF."}
    assert not list(uploads.UPLOAD_DIRECTORY.glob("*"))


def test_missing_libreoffice_returns_service_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("CVREFORM_CONVERT_DOCX_TO_PDF", "true")

    def fail_conversion(source: Path, output: Path) -> Path:
        raise DocumentConverterNotFoundError("not installed")

    monkeypatch.setattr(uploads, "convert_docx_to_pdf", fail_conversion)

    response = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("resume.docx", make_docx(), uploads.DOCX_CONTENT_TYPE)},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "DOCX-to-PDF conversion is unavailable because LibreOffice is not installed."
    }
    assert not list(uploads.UPLOAD_DIRECTORY.glob("*"))


def test_reject_unsupported_file_type() -> None:
    response = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("resume.txt", b"CV content", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json() == {"detail": "Only DOCX files are supported."}


def test_reject_pdf_file() -> None:
    response = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("resume.pdf", b"%PDF-1.7", "application/pdf")},
    )

    assert response.status_code == 415
    assert response.json() == {"detail": "Only DOCX files are supported."}


def test_reject_docx_when_only_pdf_is_enabled(monkeypatch) -> None:
    monkeypatch.setenv("CVREFORM_ACCEPT_DOCX", "false")
    monkeypatch.setenv("CVREFORM_ACCEPT_PDF", "true")

    response = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("resume.docx", make_docx(), uploads.DOCX_CONTENT_TYPE)},
    )

    assert response.status_code == 415
    assert response.json() == {"detail": "Only PDF files are supported."}


def test_reject_all_uploads_when_both_types_are_disabled(monkeypatch) -> None:
    monkeypatch.setenv("CVREFORM_ACCEPT_DOCX", "false")
    monkeypatch.setenv("CVREFORM_ACCEPT_PDF", "false")

    response = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("resume.docx", make_docx(), uploads.DOCX_CONTENT_TYPE)},
    )

    assert response.status_code == 415
    assert response.json() == {"detail": "CV uploads are disabled by configuration."}


def test_reject_invalid_docx_content() -> None:
    response = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("resume.docx", b"not a docx", uploads.DOCX_CONTENT_TYPE)},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "The uploaded file is not a valid DOCX document."}


def test_reject_empty_file() -> None:
    response = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("resume.docx", b"", uploads.DOCX_CONTENT_TYPE)},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "The uploaded file is empty."}


def test_reject_file_over_size_limit() -> None:
    content = b"x" * (uploads.MAX_UPLOAD_SIZE + 1)

    response = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("large.docx", content, uploads.DOCX_CONTENT_TYPE)},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "The uploaded file exceeds the 10 MB limit."}


def test_reconstruct_endpoint_runs_processing_pipeline(monkeypatch) -> None:
    monkeypatch.setenv("CVREFORM_ACCEPT_PDF", "true")
    upload = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("resume.pdf", b"%PDF-1.7\nCV", uploads.PDF_CONTENT_TYPE)},
    ).json()
    upload_id = upload["upload_id"]
    asset = ExtractedAsset(
        asset_id="asset-001",
        filename="asset-001.png",
        media_type="image/png",
        width=100,
        height=80,
        size=7,
        sha256="digest",
        pages=(1,),
        source_names=("image",),
    )
    document = CVHTMLResult(
        html='<article class="cv-document"><img src="asset" /></article>',
        css=".cv-document { color: black; }",
        warnings=[],
    )
    processing = AsyncMock()
    processing.process.return_value = CVProcessingResult(
        document=document,
        asset_extraction=AssetExtractionResult(assets=(asset,), warnings=()),
        links=(
            ExtractedLink(
                link_id="link-001",
                destination="https://example.com",
                pages=(1,),
                source_names=("PDF link annotation",),
            ),
        ),
        output_directory=uploads.PROCESSED_DIRECTORY / upload_id,
    )
    app.dependency_overrides[get_cv_processing_service] = lambda: processing

    response = client.post(f"/api/v1/cvs/{upload_id}/reconstruct")

    assert response.status_code == 200
    assert response.json()["html"] == document.html
    assert response.json()["assets"][0]["filename"] == "asset-001.png"
    assert response.json()["verified_link_count"] == 1
    processing.process.assert_awaited_once_with(
        source_document=uploads.UPLOAD_DIRECTORY / f"{upload_id}.pdf",
        pdf_document=uploads.UPLOAD_DIRECTORY / f"{upload_id}.pdf",
        output_directory=uploads.PROCESSED_DIRECTORY / upload_id,
        asset_url_prefix=f"/api/v1/cvs/{upload_id}/assets",
    )


def test_reconstruct_docx_requires_converted_pdf() -> None:
    upload = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("resume.docx", make_docx(), uploads.DOCX_CONTENT_TYPE)},
    ).json()

    response = client.post(f"/api/v1/cvs/{upload['upload_id']}/reconstruct")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "This CV must be converted to PDF before reconstruction."
    }
