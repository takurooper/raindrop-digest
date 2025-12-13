from __future__ import annotations

import logging
from typing import Tuple, List
from urllib.parse import urlparse

import httpx
from lxml import html
from readability import Document

from .config import IMAGE_TEXT_THRESHOLD, IMAGE_WORD_THRESHOLD, MAX_EXTRACT_CHARS
from .models import ExtractedContent
from .utils import count_words, is_cjk_text, trim_text

logger = logging.getLogger(__name__)

USER_AGENT = "RaindropSummarizer/0.1 (+github.com/user)"


class ExtractionError(Exception):
    """Raised when content extraction fails."""


def detect_source(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host.endswith("x.com") or host.endswith("twitter.com"):
        return "x"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    return "web"


def fetch_html(url: str) -> str:
    logger.info("Fetching URL: %s", url)
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=20.0, follow_redirects=True) as client:
        try:
            response = client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExtractionError(f"HTTP fetch failed: {exc}") from exc
        return response.text


def extract_text(url: str) -> ExtractedContent:
    source = detect_source(url)
    if source == "x":
        raise ExtractionError("Xリンクは手動確認対象のため自動要約しません。")
    if source == "youtube":
        raise ExtractionError("YouTubeリンクは手動確認対象のため自動要約しません。")
    html_text = fetch_html(url)
    text = _extract_readability(html_text, url)
    cleaned = text.strip()
    if not cleaned:
        raise ExtractionError("Extracted text is empty.")
    trimmed = trim_text(cleaned, MAX_EXTRACT_CHARS)
    images = None
    image_extraction_attempted = False
    should_attempt_images = False
    if is_cjk_text(trimmed):
        should_attempt_images = len(trimmed) <= IMAGE_TEXT_THRESHOLD
    else:
        should_attempt_images = count_words(trimmed) <= IMAGE_WORD_THRESHOLD

    if should_attempt_images:
        images = _extract_images_from_html(html_text)
        image_extraction_attempted = True
    logger.info(
        "Extracted %s characters from %s (source=%s)%s",
        len(trimmed),
        url,
        source,
        "" if image_extraction_attempted else " (image extraction skipped: text too long)",
    )
    return ExtractedContent(
        text=trimmed,
        source=source,
        length=len(trimmed),
        images=images,
        image_extraction_attempted=image_extraction_attempted,
    )


def _extract_youtube(html_text: str) -> Tuple[str, List[str]]:
    tree = html.fromstring(html_text)
    title = tree.findtext(".//title") or ""
    description_nodes = tree.xpath("//meta[@name='description']/@content")
    description = description_nodes[0] if description_nodes else ""
    combined = "\n".join(filter(None, [title.strip(), description.strip()]))
    return combined, []


def _extract_x(html_text: str) -> str:
    tree = html.fromstring(html_text)
    og_description = tree.xpath("//meta[@property='og:description']/@content")
    description = og_description[0] if og_description else ""
    if not description:
        raise ExtractionError("Failed to extract X post content.")
    return description


def _extract_readability(html_text: str, url: str) -> str:
    doc = Document(html_text, url=url)
    summary_html = doc.summary(html_partial=True)
    tree = html.fromstring(summary_html)
    text = tree.text_content()
    return text


def _extract_images_from_html(html_text: str) -> List[str]:
    tree = html.fromstring(html_text)
    raw_urls = tree.xpath("//img/@src")
    filtered = _filter_image_urls(raw_urls)
    return filtered


def _filter_image_urls(urls: List[str]) -> List[str]:
    allowed_ext = (".jpg", ".jpeg", ".png", ".webp", ".gif")
    blocked_keywords = ("facebook.com/tr?", "doubleclick", "adsystem", "pixel", "analytics", "collect")
    cleaned: List[str] = []
    for url in urls:
        if not url:
            continue
        lower = url.lower()
        if not (lower.startswith("http://") or lower.startswith("https://")):
            continue
        if any(bad in lower for bad in blocked_keywords):
            continue
        base = lower.split("?", 1)[0]
        if not any(base.endswith(ext) for ext in allowed_ext):
            continue
        cleaned.append(url)
    return cleaned[:5]
