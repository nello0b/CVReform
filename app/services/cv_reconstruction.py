"""Reconstruct editable CV HTML and CSS from a PDF using OpenAI."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING

from openai import OpenAIError

from app.prompts.cv_to_html import CV_TO_HTML_INSTRUCTIONS, CV_TO_HTML_PROMPT_VERSION
from app.schemas.cv_html import CVHTMLResult
from app.services.openai_client import OpenAIClient, get_openai_client

if TYPE_CHECKING:
    from app.services.document_asset_extractor import ExtractedAsset
    from app.services.document_link_extractor import ExtractedLink
    from app.services.pdf_page_renderer import RenderedPDFPage

MAX_OPENAI_FILE_BYTES = 50 * 1024 * 1024


class CVReconstructionError(RuntimeError):
    """Raised when a PDF cannot be reconstructed into a validated document."""


class CVReconstructionRefusedError(CVReconstructionError):
    """Raised when the model refuses to process the supplied document."""


class CVReconstructionService:
    """Turn one local PDF into schema-validated editable HTML and CSS."""

    def __init__(self, client: OpenAIClient | None = None) -> None:
        self._client = client or get_openai_client()

    async def reconstruct_pdf(
        self,
        source: Path,
        *,
        assets: tuple[ExtractedAsset, ...] = (),
        assets_directory: Path | None = None,
        asset_url_prefix: str = "assets",
        links: tuple[ExtractedLink, ...] = (),
        page_images: tuple[RenderedPDFPage, ...] = (),
        page_images_directory: Path | None = None,
    ) -> CVHTMLResult:
        """Send a PDF to OpenAI and return its validated HTML/CSS reconstruction."""

        source = source.resolve()
        self._validate_pdf(source)
        if assets and assets_directory is None:
            raise CVReconstructionError(
                "An assets directory is required when extracted assets are supplied."
            )
        if page_images and page_images_directory is None:
            raise CVReconstructionError(
                "A page-images directory is required when page images are supplied."
            )

        # A data URL keeps this one-shot request self-contained and avoids leaving an
        # uploaded copy in the Files API. `store=False` also disables response storage.
        encoded_pdf = base64.b64encode(source.read_bytes()).decode("ascii")
        content: list[dict[str, str]] = [
            {
                "type": "input_file",
                "filename": source.name,
                "file_data": f"data:application/pdf;base64,{encoded_pdf}",
                "detail": "high",
            },
            {
                "type": "input_text",
                "text": (
                    "Reconstruct this CV using the supplied instructions. "
                    "Extracted image assets, when present, follow below."
                ),
            },
        ]

        if page_images_directory is not None:
            page_count = len(page_images)
            for page_image in page_images:
                page_path = page_images_directory / page_image.filename
                encoded_page = base64.b64encode(page_path.read_bytes()).decode("ascii")
                css_width = round(page_image.width * 96 / page_image.dpi)
                css_height = round(page_image.height * 96 / page_image.dpi)
                content.extend(
                    [
                        {
                            "type": "input_text",
                            "text": (
                                "FULL-PAGE VISUAL REFERENCE: "
                                f"PDF page {page_image.page_number} of {page_count}. "
                                f"This {page_image.width}x{page_image.height} raster image was "
                                f"rendered at {page_image.dpi} DPI and corresponds to an "
                                f"approximately {css_width}x{css_height} CSS-pixel page at the "
                                "browser standard of 96 CSS pixels per inch. Do not interpret "
                                "raster pixels as CSS pixels one-to-one. "
                                "Use this screenshot as the primary reference for that "
                                "page's layout and styling. It is not a reusable image "
                                "asset and must not appear in the output HTML."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": (
                                f"data:{page_image.media_type};base64,{encoded_page}"
                            ),
                            "detail": "high",
                        },
                    ]
                )

        if assets_directory is not None:
            for asset in assets:
                asset_path = assets_directory / asset.filename
                encoded_asset = base64.b64encode(asset_path.read_bytes()).decode("ascii")
                relative_path = f"{asset_url_prefix.rstrip('/')}/{asset.filename}"
                content.extend(
                    [
                        {
                            "type": "input_text",
                            "text": (
                                f"Extracted asset {asset.asset_id}: use relative path "
                                f"{relative_path} only if it matches the PDF."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": f"data:{asset.media_type};base64,{encoded_asset}",
                            "detail": "high",
                        },
                    ]
                )

        if links:
            link_manifest = "\n".join(
                (
                    f"- {link.link_id}: destination={link.destination!r}; "
                    f"pages={list(link.pages) or 'unknown'}"
                )
                for link in links
            )
            content.append(
                {
                    "type": "input_text",
                    "text": (
                        "Verified hyperlink destinations extracted from the original "
                        f"document:\n{link_manifest}"
                    ),
                }
            )

        try:
            response = await self._client.create_parsed_response(
                CVHTMLResult,
                instructions=CV_TO_HTML_INSTRUCTIONS,
                input=[
                    {
                        "role": "user",
                        "content": content,
                    }
                ],
                metadata={"prompt_version": CV_TO_HTML_PROMPT_VERSION},
                store=False,
            )
        except OpenAIError as error:
            raise CVReconstructionError("OpenAI could not reconstruct the CV.") from error

        if response.output_parsed is not None:
            return response.output_parsed

        refusal = _find_refusal(response.output)
        if refusal:
            raise CVReconstructionRefusedError(
                "The model refused to reconstruct this document."
            )

        raise CVReconstructionError(
            "OpenAI returned no schema-valid CV reconstruction."
        )

    @staticmethod
    def _validate_pdf(source: Path) -> None:
        if not source.is_file():
            raise CVReconstructionError(f"PDF source file does not exist: {source}")
        if source.suffix.lower() != ".pdf":
            raise CVReconstructionError("CV reconstruction currently accepts PDF files only.")
        if source.stat().st_size == 0:
            raise CVReconstructionError("The PDF is empty.")
        if source.stat().st_size > MAX_OPENAI_FILE_BYTES:
            raise CVReconstructionError("The PDF exceeds OpenAI's 50 MB file limit.")


def _find_refusal(output: object) -> str | None:
    """Find a refusal without depending on private CV text or a specific SDK subclass."""

    for output_item in output if isinstance(output, list) else []:
        for content_item in getattr(output_item, "content", []):
            refusal = getattr(content_item, "refusal", None)
            if refusal:
                return str(refusal)
    return None
