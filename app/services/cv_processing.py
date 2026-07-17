"""Coordinate deterministic asset extraction with AI CV reconstruction."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings, get_settings
from app.schemas.cv_html import CVHTMLResult
from app.services.cv_reconstruction import CVReconstructionService
from app.services.document_asset_extractor import (
    AssetExtractionResult,
    extract_document_assets,
)
from app.services.document_link_extractor import ExtractedLink, extract_document_links
from app.services.pdf_page_renderer import (
    PDFPageRenderingResult,
    render_pdf_pages,
)


@dataclass(frozen=True)
class CVProcessingResult:
    document: CVHTMLResult
    asset_extraction: AssetExtractionResult
    links: tuple[ExtractedLink, ...]
    output_directory: Path
    page_rendering: PDFPageRenderingResult | None = None


class CVProcessingService:
    """Run the complete local-assets plus OpenAI reconstruction stage."""

    def __init__(
        self,
        reconstruction_service: CVReconstructionService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._reconstruction_service = reconstruction_service or CVReconstructionService()
        self._settings = settings or get_settings()

    async def process(
        self,
        *,
        source_document: Path,
        pdf_document: Path,
        output_directory: Path,
        asset_url_prefix: str = "assets",
    ) -> CVProcessingResult:
        """Extract original assets, reconstruct the PDF, and save editable output."""

        assets_directory = output_directory / "assets"
        asset_extraction = await asyncio.to_thread(
            extract_document_assets,
            source_document,
            assets_directory,
        )
        links = await asyncio.to_thread(extract_document_links, source_document)

        page_rendering: PDFPageRenderingResult | None = None
        if self._settings.cvreform_send_page_images:
            page_rendering = await asyncio.to_thread(
                render_pdf_pages,
                pdf_document,
                output_directory / "page-images",
                dpi=self._settings.cvreform_page_image_dpi,
            )

        document = await self._reconstruction_service.reconstruct_pdf(
            pdf_document,
            assets=asset_extraction.assets,
            assets_directory=assets_directory,
            asset_url_prefix=asset_url_prefix,
            links=links,
            page_images=page_rendering.pages if page_rendering else (),
            page_images_directory=page_rendering.output_directory if page_rendering else None,
        )

        output_directory.mkdir(parents=True, exist_ok=True)
        (output_directory / "document.html").write_text(document.html, encoding="utf-8")
        (output_directory / "styles.css").write_text(document.css, encoding="utf-8")

        combined_warnings = [*asset_extraction.warnings, *document.warnings]
        if combined_warnings != document.warnings:
            document = document.model_copy(update={"warnings": combined_warnings})

        return CVProcessingResult(
            document=document,
            asset_extraction=asset_extraction,
            links=links,
            output_directory=output_directory,
            page_rendering=page_rendering,
        )


def get_cv_processing_service() -> CVProcessingService:
    """Build the processing dependency used by the reconstruction route."""

    return CVProcessingService()
