from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Protocol

import httpx
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Email, Mail

logger = logging.getLogger(__name__)


class MailError(Exception):
    """Raised when mail sending fails."""


class MailSender(Protocol):
    provider: str

    def send(self, subject: str, text_body: str, html_body: str | None = None) -> None: ...


@dataclass(frozen=True)
class MailConfig:
    from_email: str
    from_name: str
    to_email: str


class SendGridMailer:
    provider = "sendgrid"

    def __init__(self, api_key: str, config: MailConfig):
        self._client = SendGridAPIClient(api_key)
        self._from_email = Email(email=config.from_email, name=config.from_name)
        self._to_email = config.to_email

    def send(self, subject: str, text_body: str, html_body: str | None = None) -> None:
        mail = Mail(
            from_email=self._from_email,
            to_emails=self._to_email,
            subject=subject,
            plain_text_content=text_body,
            html_content=html_body,
        )
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                response = self._client.send(mail)
                if response.status_code in {502, 503, 504} and attempt == 0:
                    logger.warning("SendGrid transient error (status=%s); retrying once", response.status_code)
                    continue
                if response.status_code >= 400:
                    raise MailError(f"SendGrid returned error status: {response.status_code}")
                logger.info("Mail sent with status %s", response.status_code)
                return
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                status_code = getattr(exc, "status_code", None)
                if isinstance(status_code, int) and status_code in {502, 503, 504} and attempt == 0:
                    logger.warning("SendGrid transient exception (status=%s); retrying once", status_code)
                    continue
                break
        raise MailError(f"Failed to send email: {last_exc}") from last_exc


class BrevoMailer:
    provider = "brevo"

    def __init__(self, api_key: str, config: MailConfig):
        self._api_key = api_key
        self._config = config

    def send(self, subject: str, text_body: str, html_body: str | None = None) -> None:
        payload = {
            "sender": {"name": self._config.from_name, "email": self._config.from_email},
            "to": [{"email": self._config.to_email}],
            "subject": subject,
            "textContent": text_body,
        }
        if html_body:
            payload["htmlContent"] = html_body

        headers = {"api-key": self._api_key, "content-type": "application/json"}
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                with httpx.Client(timeout=20.0) as client:
                    response = client.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers)
                if response.status_code in {502, 503, 504} and attempt == 0:
                    logger.warning("Brevo transient error (status=%s); retrying once", response.status_code)
                    continue
                response.raise_for_status()
                logger.info("Mail sent with status %s", response.status_code)
                return
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt == 0:
                    continue
                break
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status = exc.response.status_code
                if status in {502, 503, 504} and attempt == 0:
                    logger.warning("Brevo transient error (status=%s); retrying once", status)
                    continue
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                break
        raise MailError(f"Failed to send email: {last_exc}") from last_exc


def build_mailer(
    *,
    brevo_api_key: Optional[str],
    sendgrid_api_key: Optional[str],
    from_email: str,
    from_name: str,
    to_email: str,
) -> MailSender:
    """
    Provider selection:
    - Brevo is default.
    - If both are set, use Brevo.
    - Otherwise use whichever is set.
    """
    config = MailConfig(from_email=from_email, from_name=from_name, to_email=to_email)
    if brevo_api_key and brevo_api_key.strip():
        return BrevoMailer(brevo_api_key.strip(), config)
    if sendgrid_api_key and sendgrid_api_key.strip():
        return SendGridMailer(sendgrid_api_key.strip(), config)
    raise MailError("No mail provider configured: set BREVO_API_KEY or SENDGRID_API_KEY.")
