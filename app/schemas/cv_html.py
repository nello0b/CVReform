from pydantic import BaseModel, ConfigDict, Field


class CVHTMLResult(BaseModel):
    """Structured result produced when the AI reconstructs a CV from a PDF."""

    model_config = ConfigDict(extra="forbid")

    html: str = Field(
        description=(
            "Safe editable HTML fragment rooted at one article.cv-document element."
        )
    )
    css: str = Field(
        description="Printable CSS whose selectors are scoped beneath .cv-document."
    )
    warnings: list[str] = Field(
        description="Uncertain or unsupported visual details found during reconstruction."
    )
