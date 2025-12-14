from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
import re
from typing import Iterable, List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .config import JST, TAG_CONFIRMED, TAG_DELIVERED, TAG_FAILED
from .models import RaindropItem

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_jst(dt: datetime) -> datetime:
    return dt.astimezone(JST)


def parse_raindrop_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Invalid datetime format: {value}") from exc


def is_recent(item: RaindropItem, threshold_jst: datetime) -> bool:
    created_jst = item.created.astimezone(JST)
    return created_jst >= threshold_jst


def has_excluded_tag(tags: Iterable[str]) -> bool:
    excluded = {TAG_CONFIRMED, TAG_DELIVERED, TAG_FAILED}
    return any(tag in excluded for tag in tags)


def filter_new_items(items: List[RaindropItem], threshold_jst: datetime) -> List[RaindropItem]:
    filtered: List[RaindropItem] = []
    for item in items:
        if not is_recent(item, threshold_jst):
            continue
        if has_excluded_tag(item.tags):
            continue
        filtered.append(item)
    return filtered


def append_note(original: str | None, addition: str) -> str:
    return addition


def trim_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def canonicalize_url(url: str) -> str:
    """
    Canonicalize URL to detect duplicates within a single batch run.

    - Remove common tracking parameters (utm_*, fbclid, gclid, etc.)
    - Drop fragment
    - Lowercase scheme/host
    - Sort remaining query parameters for stable comparison
    """
    parts = urlsplit(url)
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    path = parts.path or "/"

    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    filtered_pairs = [(k, v) for (k, v) in query_pairs if not _is_tracking_param(k)]
    filtered_pairs.sort(key=lambda kv: (kv[0], kv[1]))
    query = urlencode(filtered_pairs, doseq=True)

    return urlunsplit((scheme, netloc, path, query, ""))


def _is_tracking_param(key: str) -> bool:
    lowered = key.lower()
    if lowered.startswith("utm_"):
        return True
    return lowered in {
        # SNS / campaign tracking
        "fbclid",
        "gclid",
        "gclsrc",
        "gclaw",
        "gcldc",
        "igshid",
        "mc_cid",
        "mc_eid",
        "msclkid",
        "ref",
        "ref_src",
        "spm",
        # Google Analytics / link decoration
        "_gl",
        "_ga",
        "_gid",
        "_gac",
        "_gcl_au",
        "_hsenc",
        "_hsmi",
        # Common SNS/share parameters (e.g. Yahoo News)
        "source",
        "dv",
        "mid",
        "date",
        "ctg",
        "bt",
    }


def choose_preferred_duplicate(items: List[RaindropItem]) -> RaindropItem:
    """
    Choose which duplicate to keep.

    Prefer URLs with fewer query parameters and shorter total length.
    """
    if not items:
        raise ValueError("items must not be empty")

    def score(item: RaindropItem) -> tuple[int, int]:
        parts = urlsplit(item.link)
        query_count = 0 if not parts.query else len(parts.query.split("&"))
        return query_count, len(item.link)

    return min(items, key=score)


_CJK_REGEX = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]")


def is_cjk_text(text: str) -> bool:
    """
    Heuristic language check for Japanese/Chinese/Korean.

    If the text contains any Hiragana/Katakana/Han/Hangul, treat it as CJK.
    """
    return _CJK_REGEX.search(text) is not None


def count_words(text: str) -> int:
    """
    Count words for non-CJK texts (primarily English).
    """
    return len(re.findall(r"\b\w+\b", text))


def threshold_from_now(now_jst: datetime, days: int) -> datetime:
    return now_jst - timedelta(days=days)
