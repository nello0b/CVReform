import pytest
from pydantic import ValidationError

from app.schemas.cv_html import CVHTMLResult


def test_cv_html_result_accepts_the_expected_output() -> None:
    result = CVHTMLResult(
        html='<article class="cv-document"><h1>Example</h1></article>',
        css=".cv-document h1 { font-weight: 700; }",
        warnings=[],
    )

    assert result.html.startswith("<article")
    assert result.css.startswith(".cv-document")
    assert result.warnings == []


def test_cv_html_result_requires_every_field() -> None:
    with pytest.raises(ValidationError):
        CVHTMLResult(
            html='<article class="cv-document"></article>',
            css=".cv-document { display: block; }",
        )


def test_cv_html_result_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        CVHTMLResult(
            html='<article class="cv-document"></article>',
            css=".cv-document { display: block; }",
            warnings=[],
            explanation="Extra model commentary is not part of the contract.",
        )
