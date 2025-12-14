from __future__ import annotations

from datetime import datetime, timedelta, timezone

from raindrop_digest.models import RaindropItem
from raindrop_digest.utils import append_note, filter_new_items, threshold_from_now, trim_text

JST = timezone(timedelta(hours=9))


def _item(created: datetime, tags=None) -> RaindropItem:
    return RaindropItem(
        id=1,
        link="https://example.com",
        title="Example",
        created=created,
        tags=tags or [],
    )


def test_filter_new_items_excludes_old_and_tagged():
    now_jst = datetime(2024, 12, 7, tzinfo=JST)
    threshold = threshold_from_now(now_jst, 3)
    recent = _item(now_jst - timedelta(days=1))
    old = _item(now_jst - timedelta(days=5))
    tagged = _item(now_jst - timedelta(days=1), tags=["配信済み"])

    filtered = filter_new_items([recent, old, tagged], threshold)
    assert recent in filtered
    assert old not in filtered
    assert tagged not in filtered


def test_append_note_appends_with_separator():
    original = "existing note"
    addition = "new summary"
    result = append_note(original, addition)
    assert result == "new summary"


def test_trim_text_respects_limit():
    text = "a" * 5
    assert trim_text(text, 10) == text
    assert trim_text(text, 3) == "aaa"
