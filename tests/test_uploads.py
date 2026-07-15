from io import BytesIO
from pathlib import Path
from shutil import rmtree
from uuid import uuid4
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import uploads
from app.services.document_converter import (
    DocumentConversionError,
    DocumentConverterNotFoundError,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def use_temporary_upload_directory(monkeypatch):
    test_directory = Path("storage/test-uploads") / uuid4().hex
    monkeypatch.setattr(uploads, "UPLOAD_DIRECTORY", test_directory)
    for setting_name in (
        "CVREFORM_ACCEPT_DOCX",
        "CVREFORM_ACCEPT_PDF",
        "CVREFORM_CONVERT_DOCX_TO_PDF",
    ):
        monkeypatch.delenv(setting_name, raising=False)
    yield
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
