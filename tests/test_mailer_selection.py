from __future__ import annotations

import pytest

from raindrop_digest.mailer import MailError, build_mailer


def test_selects_brevo_when_brevo_key_is_set():
    mailer = build_mailer(
        brevo_api_key="brevo-key",
        sendgrid_api_key=None,
        from_email="from@example.com",
        from_name="From",
        to_email="to@example.com",
    )
    assert mailer.provider == "brevo"


def test_selects_sendgrid_when_only_sendgrid_key_is_set():
    mailer = build_mailer(
        brevo_api_key=None,
        sendgrid_api_key="sendgrid-key",
        from_email="from@example.com",
        from_name="From",
        to_email="to@example.com",
    )
    assert mailer.provider == "sendgrid"


def test_selects_brevo_when_both_keys_are_set():
    mailer = build_mailer(
        brevo_api_key="brevo-key",
        sendgrid_api_key="sendgrid-key",
        from_email="from@example.com",
        from_name="From",
        to_email="to@example.com",
    )
    assert mailer.provider == "brevo"


def test_raises_when_no_provider_configured():
    with pytest.raises(MailError):
        build_mailer(
            brevo_api_key=None,
            sendgrid_api_key=None,
            from_email="from@example.com",
            from_name="From",
            to_email="to@example.com",
        )

