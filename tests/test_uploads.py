from io import BytesIO
from pathlib import Path
from shutil import rmtree
from uuid import uuid4
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import uploads

client = TestClient(app)


@pytest.fixture(autouse=True)
def use_temporary_upload_directory(monkeypatch):
    test_directory = Path("storage/test-uploads") / uuid4().hex
    monkeypatch.setattr(uploads, "UPLOAD_DIRECTORY", test_directory)
    yield
    rmtree(test_directory, ignore_errors=True)


def make_docx() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
    return output.getvalue()


def test_upload_pdf() -> None:
    content = b"%PDF-1.7\nCV content"

    response = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("resume.pdf", content, "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "resume.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size"] == len(content)
    assert (uploads.UPLOAD_DIRECTORY / f"{body['upload_id']}.pdf").read_bytes() == content


def test_upload_docx() -> None:
    content = make_docx()

    response = client.post(
        "/api/v1/cvs/upload",
        files={
            "file": (
                "resume.docx",
                content,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "resume.docx"
    assert body["size"] == len(content)
    assert (uploads.UPLOAD_DIRECTORY / f"{body['upload_id']}.docx").exists()


def test_reject_unsupported_file_type() -> None:
    response = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("resume.txt", b"CV content", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json() == {"detail": "Only PDF and DOCX files are supported."}


def test_reject_invalid_pdf_content() -> None:
    response = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("resume.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "The uploaded file is not a valid PDF document."}


def test_reject_empty_file() -> None:
    response = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("resume.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "The uploaded file is empty."}


def test_reject_file_over_size_limit() -> None:
    content = b"%PDF-" + b"x" * uploads.MAX_UPLOAD_SIZE

    response = client.post(
        "/api/v1/cvs/upload",
        files={"file": ("large.pdf", content, "application/pdf")},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "The uploaded file exceeds the 10 MB limit."}
