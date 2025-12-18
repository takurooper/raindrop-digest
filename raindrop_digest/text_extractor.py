from __future__ import annotations

import logging
import os
from typing import Tuple, List
from urllib.parse import urljoin, urlparse

import httpx
from lxml import html
from readability import Document
from .config import MAX_EXTRACT_CHARS
from .models import ExtractedContent
from .utils import trim_text

logger = logging.getLogger(__name__)

# NOTE:
# 多くのサイトは「botっぽい User-Agent」を 403 で弾くことがあります（GitHub Actions からの取得で顕在化しやすい）。
# そのためデフォルトは一般的なブラウザUAにし、必要なら環境変数で上書きできるようにします。
DEFAULT_PRIMARY_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
DEFAULT_SECONDARY_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0"
)


class ExtractionError(Exception):
    """Raised when content extraction fails."""


def detect_source(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host.endswith("x.com") or host.endswith("twitter.com"):
        return "x"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if host.endswith("speakerdeck.com"):
        return "speakerdeck"
    return "web"


def _request_headers(user_agent: str) -> dict[str, str]:
    # 「普通のブラウザに見える」最低限のヘッダに寄せる。
    # ここを過剰に増やすとサイト依存で壊れやすいので、まずはシンプルに。
    return {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _user_agent_candidates() -> list[str]:
    env_user_agent = (os.getenv("HTTP_USER_AGENT") or "").strip()
    candidates: list[str] = []
    if env_user_agent:
        candidates.append(env_user_agent)
    candidates.extend([DEFAULT_PRIMARY_USER_AGENT, DEFAULT_SECONDARY_USER_AGENT])

    # 重複排除（順序は維持）
    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
    return unique


def fetch_html(url: str, *, transport: httpx.BaseTransport | None = None) -> str:
    logger.info("Fetching URL: %s", url)
    last_status: int | None = None
    user_agents = _user_agent_candidates()
    for idx, user_agent in enumerate(user_agents, start=1):
        with httpx.Client(
            headers=_request_headers(user_agent),
            timeout=20.0,
            follow_redirects=True,
            transport=transport,
        ) as client:
            try:
                response = client.get(url)
            except httpx.RequestError as exc:
                raise ExtractionError(f"HTTP request failed: {exc}") from exc

            last_status = response.status_code
            if response.status_code in (403, 406) and idx < len(user_agents):
                logger.warning(
                    "HTTP %s for %s; retrying with another User-Agent (attempt %s/%s)",
                    response.status_code,
                    url,
                    idx,
                    len(user_agents),
                )
                continue

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                hint = ""
                if exc.response.status_code == 403:
                    hint = " (site may block automated fetch; try setting HTTP_USER_AGENT to a browser UA)"
                raise ExtractionError(f"HTTP fetch failed: {exc}{hint}") from exc
            return response.text

    raise ExtractionError(f"HTTP fetch failed: status={last_status}")


def extract_text(url: str) -> ExtractedContent:
    source = detect_source(url)
    if source == "x":
        raise ExtractionError("Xリンクは非対応です。対応を希望する場合は、開発者までご連絡ください。")
    if source == "youtube":
        raise ExtractionError("YouTubeリンクは非対応です。対応を希望する場合は、開発者までご連絡ください。")
    if source == "speakerdeck":
        raise ExtractionError("SpeakerDeckリンクは非対応です。対応を希望する場合は、開発者までご連絡ください。")
    html_text = fetch_html(url)
    text = _extract_readability(html_text, url)
    hero_image_url = _extract_hero_image_url(html_text, url)
    cleaned = text.strip()
    if not cleaned:
        raise ExtractionError("Extracted text is empty.")
    trimmed = trim_text(cleaned, MAX_EXTRACT_CHARS)
    logger.info(
        "Extracted %s characters from %s (source=%s)%s",
        len(trimmed),
        url,
        source,
        "" if not hero_image_url else " (hero image detected)",
    )
    return ExtractedContent(
        text=trimmed,
        source=source,
        length=len(trimmed),
        hero_image_url=hero_image_url,
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


def _extract_hero_image_url(html_text: str, page_url: str) -> str | None:
    """
    Extract a representative header image URL for email display.

    Prefer Open Graph / Twitter card images. If the URL is relative, resolve it using the page URL.
    """
    tree = html.fromstring(html_text)
    candidates: List[str] = []
    candidates.extend(tree.xpath("//meta[@property='og:image']/@content"))
    candidates.extend(tree.xpath("//meta[@property='og:image:url']/@content"))
    candidates.extend(tree.xpath("//meta[@property='og:image:secure_url']/@content"))
    candidates.extend(tree.xpath("//meta[@name='twitter:image']/@content"))
    candidates.extend(tree.xpath("//meta[@name='twitter:image:src']/@content"))
    candidates.extend(tree.xpath("//link[@rel='image_src']/@href"))

    for raw in candidates:
        if not raw:
            continue
        absolute = urljoin(page_url, raw)
        if _is_probably_tracking_image(absolute):
            continue
        if absolute.lower().startswith(("http://", "https://")):
            return absolute
    return None


def _is_probably_tracking_image(url: str) -> bool:
    lower = url.lower()
    blocked_keywords = (
        "facebook.com/tr?",
        "doubleclick",
        "adsystem",
        "pixel",
        "analytics",
        "collect",
        "tagmanager",
    )
    return any(bad in lower for bad in blocked_keywords)
