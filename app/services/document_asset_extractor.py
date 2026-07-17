"""Extract reusable raster assets from PDF and DOCX documents."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pikepdf
from PIL import Image, UnidentifiedImageError

MAX_ASSETS = 50
MAX_ASSET_BYTES = 10 * 1024 * 1024
MAX_TOTAL_ASSET_BYTES = 50 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
WEB_IMAGE_FORMATS = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png")}


class AssetExtractionError(RuntimeError):
    """Raised when the source document itself cannot be inspected."""


class _AssetRejectedError(ValueError):
    """Raised internally when one unsafe or unsupported asset must be skipped."""


@dataclass(frozen=True)
class ExtractedAsset:
    asset_id: str
    filename: str
    media_type: str
    width: int
    height: int
    size: int
    sha256: str
    pages: tuple[int, ...]
    source_names: tuple[str, ...]


@dataclass(frozen=True)
class AssetExtractionResult:
    assets: tuple[ExtractedAsset, ...]
    warnings: tuple[str, ...]


@dataclass
class _PendingAsset:
    content: bytes
    extension: str
    media_type: str
    width: int
    height: int
    digest: str
    pages: set[int]
    source_names: set[str]


def extract_document_assets(source: Path, output_directory: Path) -> AssetExtractionResult:
    """Extract assets from one supported document type into a controlled directory."""

    extension = source.suffix.lower()
    if extension == ".pdf":
        return extract_pdf_assets(source, output_directory)
    if extension == ".docx":
        return extract_docx_assets(source, output_directory)
    raise AssetExtractionError("Asset extraction supports only PDF and DOCX documents.")


def extract_pdf_assets(source: Path, output_directory: Path) -> AssetExtractionResult:
    """Extract embedded PDF raster images using pikepdf."""

    source = source.resolve()
    if not source.is_file():
        raise AssetExtractionError(f"PDF source file does not exist: {source}")

    pending: dict[str, _PendingAsset] = {}
    warnings: list[str] = []

    try:
        with pikepdf.Pdf.open(source) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                for source_name, image_object in page.get_images(recursive=True).items():
                    if len(pending) >= MAX_ASSETS:
                        warnings.append(f"Stopped after the {MAX_ASSETS}-asset limit.")
                        return _write_assets(pending, output_directory, warnings)

                    try:
                        stream = BytesIO()
                        extracted_extension = pikepdf.PdfImage(image_object).extract_to(
                            stream=stream,
                            apply_decode_array=True,
                            apply_mask=True,
                        )
                        _add_pending_asset(
                            pending,
                            stream.getvalue(),
                            source_name=str(source_name),
                            page_number=page_number,
                            format_hint=extracted_extension,
                        )
                    except (OSError, RuntimeError, ValueError, _AssetRejectedError) as error:
                        warnings.append(
                            f"Skipped PDF image {source_name} on page {page_number}: {error}"
                        )
    except (pikepdf.PdfError, OSError) as error:
        raise AssetExtractionError(f"The PDF could not be inspected: {error}") from error

    return _write_assets(pending, output_directory, warnings)


def extract_docx_assets(source: Path, output_directory: Path) -> AssetExtractionResult:
    """Extract raster files stored in a DOCX package's word/media directory."""

    source = source.resolve()
    if not source.is_file():
        raise AssetExtractionError(f"DOCX source file does not exist: {source}")

    pending: dict[str, _PendingAsset] = {}
    warnings: list[str] = []
    total_uncompressed_bytes = 0

    try:
        with ZipFile(source) as archive:
            media_entries = [
                entry
                for entry in archive.infolist()
                if not entry.is_dir() and entry.filename.lower().startswith("word/media/")
            ]

            for entry in media_entries:
                if len(pending) >= MAX_ASSETS:
                    warnings.append(f"Stopped after the {MAX_ASSETS}-asset limit.")
                    break
                if entry.file_size > MAX_ASSET_BYTES:
                    warnings.append(
                        f"Skipped DOCX asset {Path(entry.filename).name}: file is too large."
                    )
                    continue

                total_uncompressed_bytes += entry.file_size
                if total_uncompressed_bytes > MAX_TOTAL_ASSET_BYTES:
                    warnings.append("Stopped because DOCX media exceeded the total size limit.")
                    break

                try:
                    _add_pending_asset(
                        pending,
                        archive.read(entry),
                        source_name=Path(entry.filename).name,
                        format_hint=Path(entry.filename).suffix,
                    )
                except (OSError, ValueError, _AssetRejectedError) as error:
                    warnings.append(
                        f"Skipped DOCX asset {Path(entry.filename).name}: {error}"
                    )
    except (BadZipFile, OSError) as error:
        raise AssetExtractionError(f"The DOCX package could not be inspected: {error}") from error

    return _write_assets(pending, output_directory, warnings)


def _add_pending_asset(
    pending: dict[str, _PendingAsset],
    content: bytes,
    *,
    source_name: str,
    page_number: int | None = None,
    format_hint: str = "",
) -> None:
    normalized, extension, media_type, width, height = _prepare_web_image(
        content,
        format_hint=format_hint,
    )
    digest = sha256(normalized).hexdigest()

    if digest not in pending:
        pending[digest] = _PendingAsset(
            content=normalized,
            extension=extension,
            media_type=media_type,
            width=width,
            height=height,
            digest=digest,
            pages=set(),
            source_names=set(),
        )

    asset = pending[digest]
    asset.source_names.add(source_name)
    if page_number is not None:
        asset.pages.add(page_number)


def _prepare_web_image(
    content: bytes,
    *,
    format_hint: str,
) -> tuple[bytes, str, str, int, int]:
    if not content:
        raise _AssetRejectedError("image is empty")
    if len(content) > MAX_ASSET_BYTES:
        raise _AssetRejectedError("image exceeds the compressed size limit")

    try:
        with Image.open(BytesIO(content)) as image:
            width, height = image.size
            if width <= 0 or height <= 0:
                raise _AssetRejectedError("image dimensions are invalid")
            if width * height > MAX_IMAGE_PIXELS:
                raise _AssetRejectedError("image exceeds the decoded pixel limit")

            image.load()
            image_format = (image.format or format_hint.lstrip(".")).upper()
            if image_format in WEB_IMAGE_FORMATS:
                extension, media_type = WEB_IMAGE_FORMATS[image_format]
                return content, extension, media_type, width, height

            # Convert static non-web raster formats to PNG for safe browser display.
            converted = BytesIO()
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
            image.save(converted, format="PNG")
            return converted.getvalue(), "png", "image/png", width, height
    except (Image.DecompressionBombError, UnidentifiedImageError) as error:
        raise _AssetRejectedError("unsupported or unsafe raster image") from error


def _write_assets(
    pending: dict[str, _PendingAsset],
    output_directory: Path,
    warnings: list[str],
) -> AssetExtractionResult:
    output_directory.mkdir(parents=True, exist_ok=True)
    assets: list[ExtractedAsset] = []

    for index, asset in enumerate(pending.values(), start=1):
        asset_id = f"asset-{index:03d}"
        filename = f"{asset_id}.{asset.extension}"
        (output_directory / filename).write_bytes(asset.content)
        assets.append(
            ExtractedAsset(
                asset_id=asset_id,
                filename=filename,
                media_type=asset.media_type,
                width=asset.width,
                height=asset.height,
                size=len(asset.content),
                sha256=asset.digest,
                pages=tuple(sorted(asset.pages)),
                source_names=tuple(sorted(asset.source_names)),
            )
        )

    return AssetExtractionResult(assets=tuple(assets), warnings=tuple(warnings))
