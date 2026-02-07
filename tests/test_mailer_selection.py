from __future__ import annotations

import pytest

from raindrop_digest.mailer import MailError, build_mailer


def test_selects_ses_when_region_is_set():
    mailer = build_mailer(
        aws_region="ap-northeast-1",
        aws_access_key_id=None,
        aws_secret_access_key=None,
        aws_session_token=None,
        from_email="from@example.com",
        from_name="From",
        to_email="to@example.com",
    )
    assert mailer.provider == "ses"


def test_raises_when_region_missing():
    with pytest.raises(MailError):
        build_mailer(
            aws_region=None,
            aws_access_key_id=None,
            aws_secret_access_key=None,
            aws_session_token=None,
            from_email="from@example.com",
            from_name="From",
            to_email="to@example.com",
        )
