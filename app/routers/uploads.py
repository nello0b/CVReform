from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

router = APIRouter(prefix="/cvs", tags=["CV uploads"])

MAX_UPLOAD_SIZE = 10 * 1024 * 1024
UPLOAD_DIRECTORY = Path("storage/uploads")
SUPPORTED_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class CVUploadResponse(BaseModel):
    upload_id: str
    filename: str
    content_type: str
    size: int


def _safe_original_filename(filename: str) -> str:
    """Remove any client-provided path while preserving the display name."""
    return Path(filename.replace("\\", "/")).name


def _is_valid_pdf(content: bytes) -> bool:
    return b"%PDF-" in content[:1024]


def _is_valid_docx(content: bytes) -> bool:
    try:
        with ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
    except (BadZipFile, OSError):
        return False

    return "[Content_Types].xml" in names and "word/document.xml" in names


def _validate_content(extension: str, content: bytes) -> None:
    is_valid = _is_valid_pdf(content) if extension == ".pdf" else _is_valid_docx(content)
    if not is_valid:
        document_type = extension.removeprefix(".").upper()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The uploaded file is not a valid {document_type} document.",
        )


@router.post("/upload", response_model=CVUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_cv(file: UploadFile = File(...)) -> CVUploadResponse:
    """Validate and store one PDF or DOCX CV for later processing."""
    original_filename = _safe_original_filename(file.filename or "")
    extension = Path(original_filename).suffix.lower()

    if not original_filename or extension not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF and DOCX files are supported.",
        )

    try:
        content = await file.read(MAX_UPLOAD_SIZE + 1)
    finally:
        await file.close()

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

    return CVUploadResponse(
        upload_id=upload_id,
        filename=original_filename,
        content_type=SUPPORTED_TYPES[extension],
        size=len(content),
    )
