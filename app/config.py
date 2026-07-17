from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed backend configuration loaded from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5.4-mini", alias="OPENAI_MODEL")
    openai_timeout_seconds: float = Field(
        default=60.0,
        gt=0,
        alias="OPENAI_TIMEOUT_SECONDS",
    )
    openai_max_retries: int = Field(default=2, ge=0, le=5, alias="OPENAI_MAX_RETRIES")
    openai_max_concurrent_requests: int = Field(
        default=2,
        ge=1,
        le=20,
        alias="OPENAI_MAX_CONCURRENT_REQUESTS",
    )
    cvreform_send_page_images: bool = Field(
        default=True,
        alias="CVREFORM_SEND_PAGE_IMAGES",
    )
    cvreform_page_image_dpi: int = Field(
        default=150,
        ge=72,
        le=300,
        alias="CVREFORM_PAGE_IMAGE_DPI",
    )


@lru_cache
def get_settings() -> Settings:
    """Return one validated settings object for the lifetime of this process."""

    return Settings()
