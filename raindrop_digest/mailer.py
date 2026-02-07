"""Backwards-compatible re-exports for mail sending."""

from .runner_kit.mailer import (  # noqa: F401
    MailConfig,
    MailError,
    MailSender,
    SESMailer,
    build_mailer,
)

__all__ = [
    "MailConfig",
    "MailError",
    "MailSender",
    "SESMailer",
    "build_mailer",
]
