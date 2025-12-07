from __future__ import annotations

import logging
from typing import List

from . import config
from .config import BATCH_LOOKBACK_DAYS, TAG_DELIVERED, TAG_FAILED
from .email_formatter import build_email_body, build_email_subject
from .mailer import MailError, Mailer
from .models import SummaryResult
from .raindrop_client import RaindropClient
from .summarizer import Summarizer, SummaryConnectionError, SummaryError, SummaryRateLimitError
from .text_extractor import ExtractionError, extract_text
from .utils import filter_new_items, threshold_from_now, to_jst, utc_now

logger = logging.getLogger(__name__)


def run(settings: config.Settings) -> List[SummaryResult]:
    now = utc_now()
    now_jst = to_jst(now)
    threshold = threshold_from_now(now_jst, BATCH_LOOKBACK_DAYS)

    raindrop = RaindropClient(token=settings.raindrop_token)
    summarizer = Summarizer(api_key=settings.openai_api_key, model=settings.openai_model)
    mailer = Mailer(
        api_key=settings.sendgrid_api_key,
        from_email=settings.from_email,
        from_name=settings.from_name,
        to_email=settings.to_email,
    )
    logger.info("Using OpenAI model=%s", settings.openai_model)

    failure_notified = False
    try:
        raw_items = raindrop.fetch_unsorted_items()
        targets = filter_new_items(raw_items, threshold)
        logger.info("Processing %s target items (from %s total)", len(targets), len(raw_items))

        results: List[SummaryResult] = []
        for item in targets:
            try:
                content = extract_text(item.link)
                summary_text = summarizer.summarize(content.text)
                results.append(SummaryResult(item=item, status="success", summary=summary_text))
            except SummaryRateLimitError as exc:
                logger.exception("OpenAI rate limit hit for item %s: %s", item.id, exc)
                raise
            except SummaryConnectionError as exc:
                logger.exception("OpenAI connection failed for item %s: %s", item.id, exc)
                raise
            except (ExtractionError, SummaryError) as exc:
                logger.exception("Failed to process item %s: %s", item.id, exc)
                results.append(SummaryResult(item=item, status="failed", error=str(exc)))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unexpected failure for item %s: %s", item.id, exc)
                results.append(SummaryResult(item=item, status="failed", error=str(exc)))

        subject = build_email_subject(now_jst)
        body = build_email_body(now_jst, results)
        try:
            mailer.send(subject, body)
        except MailError as exc:
            logger.exception("Mail sending failed: %s", exc)
            failure_body = f"要約メール送信に失敗しました。\nerror={exc}\n対象数={len(results)}"
            try:
                mailer.send("【失敗】要約メール送信失敗", failure_body)
                failure_notified = True
            except MailError:
                logger.exception("Failed to send failure notification email as well.")
            raise

        for result in results:
            if result.is_success() and result.summary:
                note_text = f"▼サマリー\n{result.summary}"
                raindrop.append_note_and_tags(result.item, note_text, [TAG_DELIVERED])
            else:
                error_note = f"要約失敗: {result.error}" if result.error else "要約失敗"
                raindrop.append_note_and_tags(result.item, error_note, [TAG_DELIVERED, TAG_FAILED])

        logger.info("Batch completed. Success=%s Failure=%s", _count_success(results), _count_failure(results))
        return results
    except Exception as exc:  # noqa: BLE001
        if not failure_notified:
            try:
                mailer.send("【失敗】要約メール処理失敗", f"バッチが失敗しました。\nerror={exc}")
                failure_notified = True
            except MailError:
                logger.exception("Failed to send failure notification email.")
        raise
    finally:
        raindrop.close()


def _count_success(results: List[SummaryResult]) -> int:
    return len([r for r in results if r.is_success()])


def _count_failure(results: List[SummaryResult]) -> int:
    return len([r for r in results if not r.is_success()])
