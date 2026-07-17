from app.prompts.cv_to_html import CV_TO_HTML_INSTRUCTIONS, CV_TO_HTML_PROMPT_VERSION


def test_cv_to_html_prompt_has_a_version() -> None:
    assert CV_TO_HTML_PROMPT_VERSION == "1.5"


def test_cv_to_html_prompt_preserves_content_and_editability() -> None:
    assert "Do not summarize, rewrite, correct, translate" in CV_TO_HTML_INSTRUCTIONS
    assert "data-cvreform-id" in CV_TO_HTML_INSTRUCTIONS
    assert "Do not rasterize text" in CV_TO_HTML_INSTRUCTIONS
    assert "CSS Grid" in CV_TO_HTML_INSTRUCTIONS


def test_cv_to_html_prompt_defines_safe_structured_output() -> None:
    assert "`html`" in CV_TO_HTML_INSTRUCTIONS
    assert "`css`" in CV_TO_HTML_INSTRUCTIONS
    assert "`warnings`" in CV_TO_HTML_INSTRUCTIONS
    assert "Never include scripts" in CV_TO_HTML_INSTRUCTIONS
    assert "fully scoped beneath `.cv-document`" in CV_TO_HTML_INSTRUCTIONS


def test_cv_to_html_prompt_explains_how_to_use_extracted_assets() -> None:
    assert "immediately after an `input_text` label" in CV_TO_HTML_INSTRUCTIONS
    assert "normal HTML `<img>` element" in CV_TO_HTML_INSTRUCTIONS
    assert "exactly the URL or path" in CV_TO_HTML_INSTRUCTIONS
    assert "Never put the Base64 `input_image` data" in CV_TO_HTML_INSTRUCTIONS
    assert "If a supplied asset is not visible in the PDF" in CV_TO_HTML_INSTRUCTIONS


def test_cv_to_html_prompt_preserves_multi_page_documents() -> None:
    assert "Preserve the PDF's exact page count" in CV_TO_HTML_INSTRUCTIONS
    assert '<section class="cv-page" data-page="N">' in CV_TO_HTML_INSTRUCTIONS
    assert "same page where it appears in the PDF" in CV_TO_HTML_INSTRUCTIONS
    assert "print page break after every page" in CV_TO_HTML_INSTRUCTIONS


def test_prompt_treats_page_screenshots_as_visual_references_only() -> None:
    assert "FULL-PAGE VISUAL REFERENCE" in CV_TO_HTML_INSTRUCTIONS
    assert "primary source for visual layout" in CV_TO_HTML_INSTRUCTIONS
    assert "Never reproduce it as a page background" in CV_TO_HTML_INSTRUCTIONS
    assert '`.cv-page[data-page="N"]`' in CV_TO_HTML_INSTRUCTIONS
    assert "CSS pixels = raster pixels * 96 / rendering DPI" in CV_TO_HTML_INSTRUCTIONS
    assert "Raster pixels are not CSS pixels" in CV_TO_HTML_INSTRUCTIONS
    assert "horizontal or vertical overflow" in CV_TO_HTML_INSTRUCTIONS
    assert "Never hide, clip, truncate, or omit content" in CV_TO_HTML_INSTRUCTIONS


def test_cv_to_html_prompt_handles_optional_images_and_verified_links() -> None:
    assert "Many CVs contain no images" in CV_TO_HTML_INSTRUCTIONS
    assert "do not mention the absence of images" in CV_TO_HTML_INSTRUCTIONS
    assert "verified hyperlink destinations" in CV_TO_HTML_INSTRUCTIONS
    assert 'Never create `href="#"`' in CV_TO_HTML_INSTRUCTIONS
