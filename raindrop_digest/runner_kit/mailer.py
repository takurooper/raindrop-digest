from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Protocol

import boto3
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionClosedError,
    EndpointConnectionError,
    ReadTimeoutError,
)

logger = logging.getLogger(__name__)


class MailError(Exception):
    """Raised when mail sending fails."""


class MailSender(Protocol):
    provider: str

    def send(
        self, subject: str, text_body: str, html_body: str | None = None
    ) -> None: ...


@dataclass(frozen=True)
class MailConfig:
    from_email: str
    from_name: str
    to_email: str


class SESMailer:
    provider = "ses"

    def __init__(
        self,
        *,
        aws_region: str,
        config: MailConfig,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
    ) -> None:
        self._config = config
        client_kwargs = {"region_name": aws_region}
        if aws_access_key_id and aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = aws_access_key_id
            client_kwargs["aws_secret_access_key"] = aws_secret_access_key
            if aws_session_token:
                client_kwargs["aws_session_token"] = aws_session_token
        self._client = boto3.client("sesv2", **client_kwargs)

    def send(self, subject: str, text_body: str, html_body: str | None = None) -> None:
        body: dict[str, dict[str, str]] = {
            "Text": {"Data": text_body, "Charset": "UTF-8"}
        }
        if html_body:
            body["Html"] = {"Data": html_body, "Charset": "UTF-8"}

        request = {
            "FromEmailAddress": self._config.from_email,
            "Destination": {"ToAddresses": [self._config.to_email]},
            "Content": {
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": body,
                }
            },
        }

        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                response = self._client.send_email(**request)
                status_code = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if status_code in {502, 503, 504} and attempt == 0:
                    logger.warning(
                        "SES transient error (status=%s); retrying once",
                        status_code,
                    )
                    continue
                if isinstance(status_code, int) and status_code >= 400:
                    raise MailError(f"SES returned error status: {status_code}")
                logger.info("Mail sent with status %s", status_code)
                return
            except (
                EndpointConnectionError,
                ConnectionClosedError,
                ReadTimeoutError,
            ) as exc:
                last_exc = exc
                if attempt == 0:
                    continue
                break
            except ClientError as exc:
                last_exc = exc
                status_code = exc.response.get("ResponseMetadata", {}).get(
                    "HTTPStatusCode"
                )
                if status_code in {502, 503, 504} and attempt == 0:
                    logger.warning(
                        "SES transient error (status=%s); retrying once",
                        status_code,
                    )
                    continue
                break
            except BotoCoreError as exc:
                last_exc = exc
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                break
        raise MailError(f"Failed to send email: {last_exc}") from last_exc


def build_mailer(
    *,
    aws_region: Optional[str],
    aws_access_key_id: Optional[str],
    aws_secret_access_key: Optional[str],
    aws_session_token: Optional[str],
    from_email: str,
    from_name: str,
    to_email: str,
) -> MailSender:
    config = MailConfig(from_email=from_email, from_name=from_name, to_email=to_email)
    if not aws_region or not aws_region.strip():
        raise MailError(
            "No AWS region configured: set AWS_REGION or AWS_DEFAULT_REGION."
        )
    return SESMailer(
        aws_region=aws_region.strip(),
        aws_access_key_id=aws_access_key_id.strip() if aws_access_key_id else None,
        aws_secret_access_key=(
            aws_secret_access_key.strip() if aws_secret_access_key else None
        ),
        aws_session_token=aws_session_token.strip() if aws_session_token else None,
        config=config,
    )
