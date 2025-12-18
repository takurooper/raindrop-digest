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


def test_canonicalize_url_strips_yahoo_share_params():
    base = "https://news.yahoo.co.jp/articles/6f342ddd56d0faaf92050fd74830a730edc81cb5"
    with_share = (
        "https://news.yahoo.co.jp/articles/6f342ddd56d0faaf92050fd74830a730edc81cb5"
        "?source=sns&dv=pc&mid=other&date=20251214&ctg=bus&bt=tw_up"
    )
    assert canonicalize_url(base) == canonicalize_url(with_share)


def test_canonicalize_url_strips_ga_gl_params():
    base = "https://jabba.m-newsletter.com/posts/c0499ad9f515813f"
    with_ga = (
        "https://jabba.m-newsletter.com/posts/c0499ad9f515813f"
        "?_gl=1*e266wi*_ga*MTMzMTkwMzQxLjE3NjU2NzY5MjU."
    )
    assert canonicalize_url(base) == canonicalize_url(with_ga)


def test_canonicalize_url_strips_default_pagination_and_empty_fragment():
    with_page_1 = "https://president.jp/articles/-/106453?page=1"
    with_empty_fragment = "https://president.jp/articles/-/106453#"
    assert canonicalize_url(with_page_1) == canonicalize_url(with_empty_fragment)


def test_canonicalize_url_keeps_non_default_pagination():
    page_1 = "https://example.com/a?page=1"
    page_2 = "https://example.com/a?page=2"
    assert canonicalize_url(page_1) != canonicalize_url(page_2)


def test_canonicalize_url_strips_substack_decoration_params_custom_domain():
    url1 = (
        "https://www.a16z.news/p/a-roadmap-for-federal-ai-legislation"
        "?publication_id=13145&utm_medium=email&utm_campaign=email-share&isFreemail=true&triedRedirect=true"
    )
    url2 = (
        "https://www.a16z.news/p/a-roadmap-for-federal-ai-legislation"
        "?utm_source=substack&publication_id=13145&post_id=181801973&utm_medium=email&utm_content=share"
        "&utm_campaign=email-share&triggerShare=true&isFreemail=true&r=3m54m1&triedRedirect=true"
    )
    assert canonicalize_url(url1) == canonicalize_url(url2)


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
