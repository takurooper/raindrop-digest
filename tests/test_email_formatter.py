from __future__ import annotations

from datetime import datetime, timezone, timedelta

from raindrop_digest.email_formatter import build_email_body, build_email_subject
from raindrop_digest.models import RaindropItem, SummaryResult

JST = timezone(timedelta(hours=9))


def _item() -> RaindropItem:
    return RaindropItem(
        id=1,
        link="https://example.com",
        title="Example Title",
        created=datetime(2024, 12, 5, 12, 0, tzinfo=timezone.utc),
        tags=[],
    )


def test_build_email_subject():
    now = datetime(2024, 12, 7, tzinfo=timezone.utc)
    subject = build_email_subject(now)
    assert "2024-12-07" in subject


def test_build_email_body_success_and_failure():
    item = _item()
    success = SummaryResult(item=item, status="success", summary="Summary text")
    failure = SummaryResult(item=item, status="failed", error="oops")
    text_body, html_body = build_email_body(datetime(2024, 12, 7, tzinfo=timezone.utc), [success, failure])
    assert "Example Title" in text_body
    assert "Summary text" in text_body
    assert "要約に失敗" in text_body
    assert '<a href="https://example.com">こちらをクリック</a>' in html_body


def test_build_email_body_includes_hero_image_when_present():
    item = _item()
    success = SummaryResult(
        item=item,
        status="success",
        summary="Summary text",
        hero_image_url="https://example.com/hero.png",
    )
    _, html_body = build_email_body(datetime(2024, 12, 7, tzinfo=timezone.utc), [success])
    assert 'src="https://example.com/hero.png"' in html_body
