from __future__ import annotations

import logging
from typing import Optional

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

from .prompts import summarization_system_prompt

logger = logging.getLogger(__name__)


class SummaryError(Exception):
    """Raised when summarization fails."""


class SummaryConnectionError(SummaryError):
    """Raised when summarization fails due to upstream connection issues."""


class SummaryRateLimitError(SummaryError):
    """Raised when summarization fails due to rate limits."""


class Summarizer:
    def __init__(self, api_key: str, model: str = "gpt-4.1-mini"):
        if not model or not model.strip():
            raise ValueError("OpenAI model must be provided.")
        self._client = OpenAI(api_key=api_key)
        self._model = model.strip()

    def summarize(self, text: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": summarization_system_prompt(),
                    },
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
            )
        except RateLimitError as exc:
            raise SummaryRateLimitError(f"OpenAI rate limit: {exc}") from exc
        except (APIConnectionError, APITimeoutError) as exc:
            raise SummaryConnectionError(f"OpenAI connection failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise SummaryError(f"OpenAI API call failed: {exc}") from exc

        if not response.choices:
            raise SummaryError("OpenAI response has no choices.")
        content: Optional[str] = response.choices[0].message.content
        if not content:
            raise SummaryError("OpenAI returned empty content.")
        logger.info("Summary generated (%s chars)", len(content))
        return content.strip()
