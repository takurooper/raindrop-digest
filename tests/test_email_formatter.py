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


def test_build_email_body_uses_unsupported_format_for_x_link() -> None:
    item = _item()
    failure = SummaryResult(
        item=item,
        status="failed",
        error="Xリンクは非対応です。対応を希望する場合は、開発者までご連絡ください。",
    )
    text_body, html_body = build_email_body(datetime(2024, 12, 7, tzinfo=timezone.utc), [failure])
    assert "▼サマリー" in text_body
    assert "error: Xリンクは非対応です。" in text_body
    assert "要約に失敗" not in text_body
    assert "error: Xリンクは非対応です。" in html_body


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


def test_build_email_body_includes_short_article_disclaimer_when_under_threshold():
    item = _item()
    success = SummaryResult(
        item=item,
        status="success",
        summary="Summary text",
        source_length=999,
    )
    text_body, html_body = build_email_body(datetime(2024, 12, 7, tzinfo=timezone.utc), [success])
    assert "この記事は文字数が1000未満のため、情報量が不足している可能性があります。" in text_body
    assert "この記事は文字数が1000未満のため、情報量が不足している可能性があります。" in html_body
