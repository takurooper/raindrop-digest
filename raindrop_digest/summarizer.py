from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple, Type, TYPE_CHECKING

try:
    from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
except ModuleNotFoundError:  # pragma: no cover - fallback for environments without openai installed
    APIConnectionError = APITimeoutError = RateLimitError = None  # type: ignore[assignment]
    OpenAI = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from openai import APIConnectionError as APIConnectionErrorType
    from openai import APITimeoutError as APITimeoutErrorType
    from openai import OpenAI as OpenAIType
    from openai import RateLimitError as RateLimitErrorType
else:
    OpenAIType = Any

from .config import DEFAULT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class SummaryError(Exception):
    """Raised when summarization fails."""


class SummaryConnectionError(SummaryError):
    """Raised when summarization fails due to upstream connection issues."""


class SummaryRateLimitError(SummaryError):
    """Raised when summarization fails due to rate limits."""


class Summarizer:
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4.1-mini",
        client: Optional[OpenAIType] = None,
        system_prompt: Optional[str] = None,
    ):
        if not model or not model.strip():
            raise ValueError("OpenAI model must be provided.")
        self._client = client or self._build_client(api_key)
        self._model = model.strip()
        self._rate_limit_error, self._connection_errors = self._load_error_classes(client is None)
        self._system_prompt = (system_prompt or DEFAULT_SYSTEM_PROMPT).strip()

    @staticmethod
    def _build_client(api_key: str) -> OpenAIType:
        if OpenAI is None:  # pragma: no cover - requires openai installed
            raise SummaryError("openai package is required to create an OpenAI client.")
        return OpenAI(api_key=api_key)

    @staticmethod
    def _load_error_classes(require_openai: bool) -> Tuple[Type[Exception], Tuple[Type[Exception], ...]]:
        if RateLimitError is None or APIConnectionError is None or APITimeoutError is None:
            if require_openai:
                raise SummaryError("openai package is required for summarization.")
            return Exception, (Exception, Exception)
        return RateLimitError, (APIConnectionError, APITimeoutError)

    def summarize(self, text: str) -> str:
        logger.info("Summarization request: chars=%s", len(text))
        request_payload: Dict[str, Any] = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": self._system_prompt,
                },
                {"role": "user", "content": text},
            ],
        }
        for attempt in range(2):
            try:
                # Some newer models only accept the default temperature.
                # We omit it to maximize model compatibility.
                response = self._client.chat.completions.create(**request_payload)
                break
            except Exception as exc:  # noqa: BLE001
                status_code = _extract_status_code(exc)
                if attempt == 0 and status_code in {502, 503, 504}:
                    logger.warning("OpenAI transient error (status=%s); retrying once", status_code)
                    continue
                if isinstance(exc, self._rate_limit_error):  # type: ignore[arg-type]
                    raise SummaryRateLimitError(f"OpenAI rate limit: {exc}") from exc
                if isinstance(exc, self._connection_errors):  # type: ignore[arg-type]
                    raise SummaryConnectionError(f"OpenAI connection failed: {exc}") from exc
                raise SummaryError(f"OpenAI API call failed: {exc}") from exc

        if not response.choices:
            raise SummaryError("OpenAI response has no choices.")
        content: Optional[str] = response.choices[0].message.content
        if not content:
            raise SummaryError("OpenAI returned empty content.")
        logger.info("Summary generated (%s chars)", len(content))
        return content.strip()


def _extract_status_code(exc: Exception) -> Optional[int]:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    response = getattr(exc, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if isinstance(code, int):
            return code
    return None
