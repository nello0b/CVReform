from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.prompts.cv_to_html import CV_TO_HTML_INSTRUCTIONS, CV_TO_HTML_PROMPT_VERSION
from app.schemas.cv_html import CVHTMLResult
from app.services.cv_reconstruction import (
    CVReconstructionError,
    CVReconstructionRefusedError,
    CVReconstructionService,
)
from app.services.pdf_page_renderer import RenderedPDFPage


@pytest.mark.anyio
async def test_reconstruct_pdf_sends_private_pdf_as_structured_file_input(tmp_path) -> None:
    source = tmp_path / "resume.pdf"
    source.write_bytes(b"%PDF-private-test-content")
    expected = CVHTMLResult(
        html='<article class="cv-document"></article>',
        css=".cv-document { color: black; }",
        warnings=[],
    )
    response = SimpleNamespace(output_parsed=expected, output=[])
    client = SimpleNamespace(create_parsed_response=AsyncMock(return_value=response))
    service = CVReconstructionService(client=client)

    result = await service.reconstruct_pdf(source)

    assert result is expected
    client.create_parsed_response.assert_awaited_once()
    args, request = client.create_parsed_response.await_args
    assert args == (CVHTMLResult,)
    assert request["instructions"] == CV_TO_HTML_INSTRUCTIONS
    assert request["metadata"] == {"prompt_version": CV_TO_HTML_PROMPT_VERSION}
    assert request["store"] is False
    file_input = request["input"][0]["content"][0]
    assert file_input["type"] == "input_file"
    assert file_input["filename"] == "resume.pdf"
    assert file_input["detail"] == "high"
    assert file_input["file_data"].startswith("data:application/pdf;base64,")


@pytest.mark.anyio
async def test_reconstruct_pdf_rejects_non_pdf_before_api_call(tmp_path) -> None:
    source = tmp_path / "resume.docx"
    source.write_bytes(b"not-a-pdf")
    client = SimpleNamespace(create_parsed_response=AsyncMock())
    service = CVReconstructionService(client=client)

    with pytest.raises(CVReconstructionError, match="PDF files only"):
        await service.reconstruct_pdf(source)

    client.create_parsed_response.assert_not_awaited()


@pytest.mark.anyio
async def test_reconstruct_pdf_sends_labeled_full_page_visual_references(tmp_path) -> None:
    source = tmp_path / "resume.pdf"
    source.write_bytes(b"%PDF-private-test-content")
    page_directory = tmp_path / "pages"
    page_directory.mkdir()
    (page_directory / "page-001.png").write_bytes(b"private-page-image")
    page_image = RenderedPDFPage(
        page_number=1,
        filename="page-001.png",
        media_type="image/png",
        width=1240,
        height=1754,
        size=18,
        dpi=150,
    )
    expected = CVHTMLResult(
        html='<article class="cv-document"></article>',
        css=".cv-document { color: black; }",
        warnings=[],
    )
    response = SimpleNamespace(output_parsed=expected, output=[])
    client = SimpleNamespace(create_parsed_response=AsyncMock(return_value=response))
    service = CVReconstructionService(client=client)

    await service.reconstruct_pdf(
        source,
        page_images=(page_image,),
        page_images_directory=page_directory,
    )

    request = client.create_parsed_response.await_args.kwargs
    content = request["input"][0]["content"]
    page_label = content[2]
    page_input = content[3]
    assert page_label["type"] == "input_text"
    assert "FULL-PAGE VISUAL REFERENCE" in page_label["text"]
    assert "page 1 of 1" in page_label["text"]
    assert "1240x1754 raster image was rendered at 150 DPI" in page_label["text"]
    assert "approximately 794x1123 CSS-pixel page" in page_label["text"]
    assert "Do not interpret raster pixels as CSS pixels one-to-one" in page_label["text"]
    assert "must not appear in the output HTML" in page_label["text"]
    assert page_input["type"] == "input_image"
    assert page_input["detail"] == "high"
    assert page_input["image_url"].startswith("data:image/png;base64,")


@pytest.mark.anyio
async def test_reconstruct_pdf_reports_model_refusal(tmp_path) -> None:
    source = tmp_path / "resume.pdf"
    source.write_bytes(b"%PDF-test")
    refusal = SimpleNamespace(refusal="Cannot process this document")
    response = SimpleNamespace(
        output_parsed=None,
        output=[SimpleNamespace(content=[refusal])],
    )
    client = SimpleNamespace(create_parsed_response=AsyncMock(return_value=response))
    service = CVReconstructionService(client=client)

    with pytest.raises(CVReconstructionRefusedError, match="refused"):
        await service.reconstruct_pdf(source)
