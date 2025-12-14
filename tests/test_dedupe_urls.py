from __future__ import annotations

from datetime import datetime, timezone

from raindrop_digest.models import RaindropItem
from raindrop_digest.utils import canonicalize_url, choose_preferred_duplicate


def test_canonicalize_url_strips_utm_params():
    base = "https://www.bloomberg.com/jp/news/articles/2025-12-11/T742RDKGZAIP00?taid=693b06c20510130001f8ef78"
    with_utm = (
        "https://www.bloomberg.com/jp/news/articles/2025-12-11/T742RDKGZAIP00"
        "?taid=693b06c20510130001f8ef78&utm_campaign=trueanthem&utm_content=japan&utm_medium=social&utm_source=twitter"
    )
    assert canonicalize_url(base) == canonicalize_url(with_utm)


def test_choose_preferred_duplicate_prefers_shorter_url():
    now = datetime(2025, 12, 13, tzinfo=timezone.utc)
    item_short = RaindropItem(
        id=1,
        link="https://example.com/a?x=1",
        title="t",
        created=now,
        tags=[],
    )
    item_long = RaindropItem(
        id=2,
        link="https://example.com/a?x=1&utm_source=twitter",
        title="t",
        created=now,
        tags=[],
    )
    preferred = choose_preferred_duplicate([item_long, item_short])
    assert preferred.id == 1

