import asyncio
import logging
from functools import lru_cache
from time import perf_counter
from typing import Any, TypeVar

from openai import APIStatusError, AsyncOpenAI, OpenAIError
from openai.types.responses import ParsedResponse, Response
from pydantic import BaseModel

from app.config import Settings, get_settings

logger = logging.getLogger("uvicorn.error")
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class OpenAIConfigurationError(RuntimeError):
    """Raised when the OpenAI client cannot be configured safely."""


class OpenAIClient:
    """Small, concurrency-limited wrapper around the official asynchronous SDK."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._semaphore = asyncio.Semaphore(self.settings.openai_max_concurrent_requests)

        if client is not None:
            self._client = client
            return

        if self.settings.openai_api_key is None:
            raise OpenAIConfigurationError("OPENAI_API_KEY is not configured.")

        self._client = AsyncOpenAI(
            api_key=self.settings.openai_api_key.get_secret_value(),
            timeout=self.settings.openai_timeout_seconds,
            max_retries=self.settings.openai_max_retries,
        )

    async def create_response(self, **request: Any) -> Response:
        """Create one response without logging its prompt or document contents."""

        # Use the configured model unless a caller deliberately supplies another one.
        request.setdefault("model", self.settings.openai_model)
        model = str(request["model"])

        # Wait for an available slot before starting another paid API request.
        async with self._semaphore:
            started_at = perf_counter()

            # Log operational metadata only; `request` may contain private CV text.
            logger.info("OpenAI request started: model=%s", model)

            try:
                response = await self._client.responses.create(**request)
            except OpenAIError as error:
                # Provider metadata helps diagnose failures without exposing request contents.
                elapsed_ms = round((perf_counter() - started_at) * 1000)
                status_code = error.status_code if isinstance(error, APIStatusError) else None
                request_id = getattr(error, "request_id", None)
                logger.warning(
                    "OpenAI request failed: model=%s elapsed_ms=%d error_type=%s "
                    "status_code=%s request_id=%s",
                    model,
                    elapsed_ms,
                    type(error).__name__,
                    status_code,
                    request_id,
                )
                raise

            # Token counts let us monitor cost while keeping the generated content private.
            elapsed_ms = round((perf_counter() - started_at) * 1000)
            usage = response.usage
            logger.info(
                "OpenAI request completed: model=%s elapsed_ms=%d response_id=%s "
                "input_tokens=%s output_tokens=%s",
                model,
                elapsed_ms,
                response.id,
                usage.input_tokens if usage else None,
                usage.output_tokens if usage else None,
            )
            return response

    async def create_parsed_response(
        self,
        text_format: type[ResponseModel],
        **request: Any,
    ) -> ParsedResponse[ResponseModel]:
        """Create a response whose output is validated against a Pydantic model."""

        request.setdefault("model", self.settings.openai_model)
        model = str(request["model"])

        async with self._semaphore:
            started_at = perf_counter()
            logger.info("OpenAI structured request started: model=%s", model)

            try:
                response = await self._client.responses.parse(
                    text_format=text_format,
                    **request,
                )
            except OpenAIError as error:
                elapsed_ms = round((perf_counter() - started_at) * 1000)
                status_code = error.status_code if isinstance(error, APIStatusError) else None
                request_id = getattr(error, "request_id", None)
                logger.warning(
                    "OpenAI structured request failed: model=%s elapsed_ms=%d "
                    "error_type=%s status_code=%s request_id=%s",
                    model,
                    elapsed_ms,
                    type(error).__name__,
                    status_code,
                    request_id,
                )
                raise

            elapsed_ms = round((perf_counter() - started_at) * 1000)
            usage = response.usage
            logger.info(
                "OpenAI structured request completed: model=%s elapsed_ms=%d "
                "response_id=%s input_tokens=%s output_tokens=%s",
                model,
                elapsed_ms,
                response.id,
                usage.input_tokens if usage else None,
                usage.output_tokens if usage else None,
            )
            return response

    async def close(self) -> None:
        """Close the SDK's reusable HTTP connection pool."""

        await self._client.close()


@lru_cache
def get_openai_client() -> OpenAIClient:
    """Return the process-wide OpenAI service used by FastAPI dependencies."""

    return OpenAIClient()
