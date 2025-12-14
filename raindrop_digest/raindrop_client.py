from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

import httpx

from .config import TAG_CONFIRMED, TAG_DELIVERED, TAG_FAILED, UNSORTED_COLLECTION_ID
from .models import RaindropItem
from .utils import append_note, parse_raindrop_datetime

logger = logging.getLogger(__name__)

class RaindropError(Exception):
    """Raised when Raindrop operations fail."""


class RaindropConnectionError(RaindropError):
    """Raised when Raindrop is unreachable (network/timeout)."""


class RaindropApiError(RaindropError):
    """Raised when Raindrop returns an error response."""


class RaindropClient:
    def __init__(self, token: str, base_url: str = "https://api.raindrop.io"):
        self._client = httpx.Client(
            base_url=base_url, headers={"Authorization": f"Bearer {token}"}, timeout=20.0
        )

    def close(self) -> None:
        self._client.close()

    def fetch_unsorted_items(self, perpage: int = 50, max_pages: int = 20) -> List[RaindropItem]:
        items: List[RaindropItem] = []
        for page in range(max_pages):
            response = self._request_with_retry(
                "GET",
                f"/rest/v1/raindrops/{UNSORTED_COLLECTION_ID}",
                params={"page": page, "perpage": perpage, "sort": "-created"},
            )
            if response is None:
                logger.warning("Skipping fetch page %s due to transient errors.", page)
                break
            data = response.json()
            page_items = data.get("items", [])
            logger.info("Fetched %s items from page %s", len(page_items), page)
            for raw in page_items:
                item = self._to_model(raw)
                items.append(item)
            if len(page_items) < perpage:
                break
        return items

    def append_note_and_tags(
        self,
        item: RaindropItem,
        note_addition: Optional[str],
        extra_tags: List[str],
    ) -> None:
        merged_note = append_note(item.note, note_addition) if note_addition else item.note or ""
        merged_tags = list({*item.tags, *extra_tags})
        payload = {"note": merged_note, "tags": merged_tags}
        logger.info("Updating Raindrop item %s with tags=%s", item.id, merged_tags)
        response = self._request_with_retry("PUT", f"/rest/v1/raindrop/{item.id}", json=payload)
        if response is None:
            raise RaindropApiError("Raindrop update failed after retries (502/503/504).")

    def delete_item(self, item_id: int) -> None:
        logger.info("Deleting duplicate Raindrop item %s", item_id)
        response = self._request_with_retry("DELETE", f"/rest/v1/raindrop/{item_id}")
        if response is None:
            raise RaindropApiError("Raindrop delete failed after retries (502/503/504).")

    def _request_with_retry(self, method: str, path: str, **kwargs) -> httpx.Response | None:
        for attempt in range(2):
            try:
                response = self._client.request(method, path, **kwargs)
                response.raise_for_status()
                return response
            except httpx.RequestError as exc:
                logger.warning("Raindrop request error %s %s: %s", method, path, exc)
                if attempt == 0:
                    continue
                raise RaindropConnectionError(f"Raindrop request failed: {exc}") from exc
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in {502, 503, 504} and attempt == 0:
                    logger.warning("Raindrop transient status %s for %s %s; retrying once", status, method, path)
                    continue
                if status in {502, 503, 504}:
                    logger.warning("Raindrop transient status %s for %s %s; giving up", status, method, path)
                    return None
                raise RaindropApiError(f"Raindrop request returned error: {exc}") from exc
        return None

    @staticmethod
    def _to_model(raw: dict) -> RaindropItem:
        return RaindropItem(
            id=raw["_id"] if "_id" in raw else raw["id"],
            link=raw["link"],
            title=raw.get("title") or raw.get("domain") or raw["link"],
            created=parse_raindrop_datetime(raw["created"]),
            tags=raw.get("tags", []),
            note=raw.get("note") or None,
        )


EXCLUDED_TAGS = {TAG_CONFIRMED, TAG_DELIVERED, TAG_FAILED}
