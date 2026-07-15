import subprocess
from pathlib import Path

import pytest

from app.services import document_converter


def test_convert_docx_to_pdf_invokes_libreoffice(monkeypatch, tmp_path: Path) -> None:
    libreoffice_path = tmp_path / "soffice.exe"
    libreoffice_path.write_bytes(b"executable")
    source = tmp_path / "resume.docx"
    source.write_bytes(b"docx")
    output = tmp_path / "resume.pdf"
    captured_command: list[str] = []

    monkeypatch.setattr(document_converter, "find_libreoffice", lambda: libreoffice_path)

    def fake_run(command: list[str], **options) -> subprocess.CompletedProcess[str]:
        captured_command.extend(command)
        output_directory = Path(command[command.index("--outdir") + 1])
        (output_directory / "resume.pdf").write_bytes(b"%PDF-1.7\nconverted")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(document_converter.subprocess, "run", fake_run)

    result = document_converter.convert_docx_to_pdf(source, output)

    assert result == output.resolve()
    assert "--headless" in captured_command
    assert "pdf:writer_pdf_Export" in captured_command
    assert output.read_bytes().startswith(b"%PDF-")


def test_convert_docx_to_pdf_requires_libreoffice(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "resume.docx"
    source.write_bytes(b"docx")
    monkeypatch.setattr(document_converter, "find_libreoffice", lambda: None)

    with pytest.raises(document_converter.DocumentConverterNotFoundError):
        document_converter.convert_docx_to_pdf(source, tmp_path / "resume.pdf")


def test_convert_docx_to_pdf_reports_failed_conversion(monkeypatch, tmp_path: Path) -> None:
    libreoffice_path = tmp_path / "soffice.exe"
    libreoffice_path.write_bytes(b"executable")
    source = tmp_path / "resume.docx"
    source.write_bytes(b"docx")
    monkeypatch.setattr(document_converter, "find_libreoffice", lambda: libreoffice_path)
    monkeypatch.setattr(
        document_converter.subprocess,
        "run",
        lambda command, **options: subprocess.CompletedProcess(
            command, 1, stdout="", stderr="bad input"
        ),
    )

    with pytest.raises(document_converter.DocumentConversionError, match="bad input"):
        document_converter.convert_docx_to_pdf(source, tmp_path / "resume.pdf")
