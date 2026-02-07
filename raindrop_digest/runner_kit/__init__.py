"""Reusable runner + mail notification kit.

This directory is intended to be copy-pasted into other repos that run a daily
pipeline on GitHub Actions and send a report email.
"""

from .mailer import MailConfig, MailError, MailSender, build_mailer

__all__ = [
    "MailConfig",
    "MailError",
    "MailSender",
    "build_mailer",
]
