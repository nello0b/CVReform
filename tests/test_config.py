from pydantic import SecretStr

from app.config import Settings


def test_ai_settings_have_safe_defaults(monkeypatch) -> None:
    for name in (
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "OPENAI_TIMEOUT_SECONDS",
        "OPENAI_MAX_RETRIES",
        "OPENAI_MAX_CONCURRENT_REQUESTS",
        "CVREFORM_SEND_PAGE_IMAGES",
        "CVREFORM_PAGE_IMAGE_DPI",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.openai_api_key is None
    assert settings.openai_model == "gpt-5.4-mini"
    assert settings.openai_timeout_seconds == 60.0
    assert settings.openai_max_retries == 2
    assert settings.openai_max_concurrent_requests == 2
    assert settings.cvreform_send_page_images is True
    assert settings.cvreform_page_image_dpi == 150


def test_ai_settings_are_loaded_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "1")
    monkeypatch.setenv("OPENAI_MAX_CONCURRENT_REQUESTS", "3")

    settings = Settings(_env_file=None)

    assert isinstance(settings.openai_api_key, SecretStr)
    assert settings.openai_api_key.get_secret_value() == "test-secret"
    assert settings.openai_model == "test-model"
    assert settings.openai_timeout_seconds == 30.0
    assert settings.openai_max_retries == 1
    assert settings.openai_max_concurrent_requests == 3
    assert "test-secret" not in repr(settings)
