"""Document conversion helpers backed by LibreOffice."""

import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

DEFAULT_CONVERSION_TIMEOUT_SECONDS = 60


class DocumentConversionError(RuntimeError):
    """Raised when a document cannot be converted."""


class DocumentConverterNotFoundError(DocumentConversionError):
    """Raised when LibreOffice cannot be found."""


def find_libreoffice() -> Path | None:
    """Find LibreOffice through configuration, PATH, or standard Windows locations."""
    candidates: list[Path] = []

    configured_path = os.getenv("SOFFICE_PATH")
    if configured_path:
        candidates.append(Path(configured_path).expanduser())

    for executable_name in ("soffice.com", "soffice.exe", "soffice"):
        path_match = shutil.which(executable_name)
        if path_match:
            candidates.append(Path(path_match))

    for environment_variable in ("ProgramFiles", "ProgramFiles(x86)"):
        base_directory = os.getenv(environment_variable)
        if base_directory:
            candidates.append(
                Path(base_directory) / "LibreOffice" / "program" / "soffice.exe"
            )

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    return None


def convert_docx_to_pdf(
    source: Path,
    output: Path,
    *,
    timeout_seconds: int = DEFAULT_CONVERSION_TIMEOUT_SECONDS,
) -> Path:
    """Convert one DOCX file to PDF using an isolated LibreOffice profile."""
    source = source.resolve()
    output = output.resolve()

    if not source.is_file():
        raise DocumentConversionError(f"DOCX source file does not exist: {source}")
    if source.suffix.lower() != ".docx":
        raise DocumentConversionError("LibreOffice input must be a DOCX file.")
    if output.suffix.lower() != ".pdf":
        raise DocumentConversionError("LibreOffice output must be a PDF file.")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero.")

    libreoffice = find_libreoffice()
    if libreoffice is None:
        raise DocumentConverterNotFoundError(
            "LibreOffice was not found. Run setup.ps1 or set SOFFICE_PATH."
        )

    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        with TemporaryDirectory(prefix=".libreoffice-", dir=output.parent) as temporary:
            temporary_directory = Path(temporary)
            profile_directory = temporary_directory / "profile"
            profile_directory.mkdir()
            command = [
                str(libreoffice),
                f"-env:UserInstallation={profile_directory.resolve().as_uri()}",
                "--headless",
                "--nologo",
                "--nodefault",
                "--convert-to",
                "pdf:writer_pdf_Export",
                "--outdir",
                str(temporary_directory),
                str(source),
            ]

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )

            if result.returncode != 0:
                details = result.stderr.strip() or result.stdout.strip() or "No details provided."
                raise DocumentConversionError(f"LibreOffice conversion failed: {details}")

            generated_pdf = temporary_directory / f"{source.stem}.pdf"
            if not generated_pdf.is_file() or generated_pdf.stat().st_size == 0:
                details = result.stderr.strip() or result.stdout.strip()
                suffix = f" Details: {details}" if details else ""
                raise DocumentConversionError(
                    f"LibreOffice completed without creating a PDF.{suffix}"
                )

            generated_pdf.replace(output)
    except subprocess.TimeoutExpired as error:
        output.unlink(missing_ok=True)
        raise DocumentConversionError(
            f"LibreOffice conversion exceeded the {timeout_seconds}-second limit."
        ) from error
    except OSError as error:
        output.unlink(missing_ok=True)
        raise DocumentConversionError(f"LibreOffice could not be started: {error}") from error

    return output
