import logging
import os
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.services.document_converter import (
    DocumentConversionError,
    DocumentConverterNotFoundError,
    convert_docx_to_pdf,
)

router = APIRouter(prefix="/cvs", tags=["CV uploads"])
logger = logging.getLogger("uvicorn.error")

MAX_UPLOAD_SIZE = 10 * 1024 * 1024
UPLOAD_DIRECTORY = Path("storage/uploads")
DOCX_EXTENSION = ".docx"
DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_EXTENSION = ".pdf"
PDF_CONTENT_TYPE = "application/pdf"


def _debug_enabled() -> bool:
    return os.getenv("CVREFORM_DEBUG", "").lower() in {"1", "true", "yes", "on"}


def _environment_flag(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _accepted_extensions() -> list[str]:
    extensions: list[str] = []
    if _environment_flag("CVREFORM_ACCEPT_DOCX", default=True):
        extensions.append(DOCX_EXTENSION)
    if _environment_flag("CVREFORM_ACCEPT_PDF"):
        extensions.append(PDF_EXTENSION)
    return extensions


class CVUploadCapabilities(BaseModel):
    accept_docx: bool
    accept_pdf: bool
    convert_docx_to_pdf: bool
    accepted_extensions: list[str]


class CVUploadResponse(BaseModel):
    upload_id: str
    filename: str
    content_type: str
    size: int
    stored_filename: str
    pdf_filename: str | None


def _safe_original_filename(filename: str) -> str:
    """Remove any client-provided path while preserving the display name."""
    return Path(filename.replace("\\", "/")).name


def _is_valid_docx(content: bytes) -> bool:
    try:
        with ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
    except (BadZipFile, OSError):
        return False

    return "[Content_Types].xml" in names and "word/document.xml" in names


def _is_valid_pdf(content: bytes) -> bool:
    return b"%PDF-" in content[:1024]


def _validate_content(extension: str, content: bytes) -> None:
    is_valid = _is_valid_pdf(content) if extension == PDF_EXTENSION else _is_valid_docx(content)
    if not is_valid:
        document_type = extension.removeprefix(".").upper()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The uploaded file is not a valid {document_type} document.",
        )


@router.get("/capabilities", response_model=CVUploadCapabilities)
def get_upload_capabilities() -> CVUploadCapabilities:
    """Report optional upload features so the frontend follows backend configuration."""
    accepted_extensions = _accepted_extensions()
    accept_docx = DOCX_EXTENSION in accepted_extensions
    accept_pdf = PDF_EXTENSION in accepted_extensions
    return CVUploadCapabilities(
        accept_docx=accept_docx,
        accept_pdf=accept_pdf,
        convert_docx_to_pdf=(
            accept_docx and _environment_flag("CVREFORM_CONVERT_DOCX_TO_PDF")
        ),
        accepted_extensions=accepted_extensions,
    )


@router.post("/upload", response_model=CVUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_cv(file: UploadFile = File(...)) -> CVUploadResponse:
    """Validate and store one enabled CV format for later HTML generation."""
    original_filename = _safe_original_filename(file.filename or "")
    extension = Path(original_filename).suffix.lower()

    supported_extensions = _accepted_extensions()

    if not original_filename or extension not in supported_extensions:
        supported_names = " and ".join(
            supported_extension.removeprefix(".").upper()
            for supported_extension in reversed(supported_extensions)
        )
        detail = (
            f"Only {supported_names} files are supported."
            if supported_names
            else "CV uploads are disabled by configuration."
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=detail,
        )

    try:
        content = await file.read(MAX_UPLOAD_SIZE + 1)
    finally:
        await file.close()

    # Log safe metadata only when run.ps1 enables debug mode; never log CV contents.
    if _debug_enabled():
        logger.info(
            "[CVReform debug] Received CV: filename=%r extension=%s "
            "reported_content_type=%r size_bytes=%d",
            original_filename,
            extension,
            file.content_type or "unknown",
            len(content),
        )

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The uploaded file exceeds the 10 MB limit.",
        )

    _validate_content(extension, content)

    upload_id = uuid4().hex
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    stored_path = UPLOAD_DIRECTORY / f"{upload_id}{extension}"
    stored_path.write_bytes(content)
    pdf_path: Path | None = stored_path if extension == PDF_EXTENSION else None

    if _debug_enabled():
        logger.info(
            "[CVReform debug] Saved CV upload: upload_id=%s path=%s",
            upload_id,
            stored_path,
        )

    if extension == DOCX_EXTENSION and _environment_flag("CVREFORM_CONVERT_DOCX_TO_PDF"):
        pdf_path = UPLOAD_DIRECTORY / f"{upload_id}{PDF_EXTENSION}"
        try:
            await run_in_threadpool(convert_docx_to_pdf, stored_path, pdf_path)
        except DocumentConverterNotFoundError as error:
            stored_path.unlink(missing_ok=True)
            logger.exception("LibreOffice is unavailable for upload_id=%s", upload_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "DOCX-to-PDF conversion is unavailable because LibreOffice "
                    "is not installed."
                ),
            ) from error
        except DocumentConversionError as error:
            stored_path.unlink(missing_ok=True)
            pdf_path.unlink(missing_ok=True)
            logger.exception("DOCX-to-PDF conversion failed for upload_id=%s", upload_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The DOCX file could not be converted to PDF.",
            ) from error

        if _debug_enabled():
            logger.info(
                "[CVReform debug] Converted DOCX to PDF: upload_id=%s source=%s output=%s",
                upload_id,
                stored_path,
                pdf_path,
            )

    return CVUploadResponse(
        upload_id=upload_id,
        filename=original_filename,
        content_type=PDF_CONTENT_TYPE if extension == PDF_EXTENSION else DOCX_CONTENT_TYPE,
        size=len(content),
        stored_filename=stored_path.name,
        pdf_filename=pdf_path.name if pdf_path else None,
    )
