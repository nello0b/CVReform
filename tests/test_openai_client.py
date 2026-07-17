import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openai import APIConnectionError
from pydantic import SecretStr

from app.config import Settings
from app.services.openai_client import OpenAIClient, OpenAIConfigurationError


def _settings(**overrides) -> Settings:
    values = {
        "OPENAI_API_KEY": "test-secret",
        "OPENAI_MODEL": "test-model",
        "OPENAI_TIMEOUT_SECONDS": 30,
        "OPENAI_MAX_RETRIES": 1,
        "OPENAI_MAX_CONCURRENT_REQUESTS": 2,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_client_requires_an_api_key() -> None:
    settings = _settings(OPENAI_API_KEY=None)

    with pytest.raises(OpenAIConfigurationError, match="OPENAI_API_KEY"):
        OpenAIClient(settings)


def test_client_configures_timeout_and_limited_retries() -> None:
    service = OpenAIClient(_settings())

    assert service._client.timeout == 30
    assert service._client.max_retries == 1
    assert isinstance(service.settings.openai_api_key, SecretStr)


@pytest.mark.anyio
async def test_create_response_uses_default_model_and_logs_only_metadata(caplog) -> None:
    prompt = "private CV text that must not be logged"
    response = SimpleNamespace(
        id="resp_test",
        usage=SimpleNamespace(input_tokens=12, output_tokens=4),
    )
    sdk_client = AsyncMock()
    sdk_client.responses.create.return_value = response
    service = OpenAIClient(_settings(), client=sdk_client)

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        result = await service.create_response(input=prompt)

    assert result is response
    sdk_client.responses.create.assert_awaited_once_with(input=prompt, model="test-model")
    assert "resp_test" in caplog.text
    assert "input_tokens=12" in caplog.text
    assert prompt not in caplog.text
    assert "test-secret" not in caplog.text


@pytest.mark.anyio
async def test_create_response_logs_safe_error_metadata(caplog) -> None:
    prompt = "another private CV"
    sdk_client = AsyncMock()
    sdk_client.responses.create.side_effect = APIConnectionError(request=AsyncMock())
    service = OpenAIClient(_settings(), client=sdk_client)

    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        with pytest.raises(APIConnectionError):
            await service.create_response(input=prompt)

    assert "APIConnectionError" in caplog.text
    assert prompt not in caplog.text
    assert "test-secret" not in caplog.text


@pytest.mark.anyio
async def test_create_parsed_response_uses_schema_and_safe_logging(caplog) -> None:
    from app.schemas.cv_html import CVHTMLResult

    prompt = "private PDF data that must not be logged"
    response = SimpleNamespace(
        id="resp_structured",
        usage=SimpleNamespace(input_tokens=20, output_tokens=10),
    )
    sdk_client = AsyncMock()
    sdk_client.responses.parse.return_value = response
    service = OpenAIClient(_settings(), client=sdk_client)

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        result = await service.create_parsed_response(
            CVHTMLResult,
            input=prompt,
            store=False,
        )

    assert result is response
    sdk_client.responses.parse.assert_awaited_once_with(
        text_format=CVHTMLResult,
        input=prompt,
        store=False,
        model="test-model",
    )
    assert "resp_structured" in caplog.text
    assert prompt not in caplog.text
    assert "test-secret" not in caplog.text
