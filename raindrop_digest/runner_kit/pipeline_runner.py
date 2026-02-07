from __future__ import annotations

import argparse
import logging
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .gha import github_run_url
from .mailer import MailError, build_mailer
from .stock_engine_email import DailyStockEmailSummary, build_stock_engine_success_email
from .trading_calendar import CsvHolidayCalendar, is_trading_day

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class PipelineResult:
    ok: bool
    exit_code: int
    stdout_tail: str


def _sleep_until(target: datetime, *, deadline: datetime) -> bool:
    while True:
        now = datetime.now(timezone.utc).astimezone(JST)
        if now >= target:
            return True
        if now >= deadline:
            return False
        time.sleep(min(30.0, max(1.0, (target - now).total_seconds())))


def _run_command(cmd: list[str], *, cwd: Path | None = None) -> PipelineResult:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    tail = "\n".join(combined.splitlines()[-80:]).strip()
    return PipelineResult(
        ok=proc.returncode == 0, exit_code=proc.returncode, stdout_tail=tail
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Daily pipeline runner with email notification."
    )
    parser.add_argument("--subject-prefix", default="stock-engine")
    parser.add_argument(
        "--pipeline-cmd", required=True, help='e.g. "stock-engine pipeline run"'
    )
    parser.add_argument(
        "--ready-check-cmd",
        default=None,
        help="optional command that exits 0 when data is ready (e.g. yfinance close is available)",
    )
    parser.add_argument("--ready-check-interval-seconds", type=int, default=120)
    parser.add_argument("--output-root", default="output")
    parser.add_argument(
        "--report-html",
        default="report.html",
        help="path relative to output/YYYY-MM-DD/",
    )
    parser.add_argument(
        "--holiday-file", default=None, help="CSV-like file with YYYY-MM-DD per line"
    )
    parser.add_argument("--min-time-jst", default="16:30", help="HH:MM (JST)")
    parser.add_argument("--max-wait-minutes", type=int, default=180)
    parser.add_argument("--workdir", default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s"
    )

    now_jst = datetime.now(timezone.utc).astimezone(JST)
    d = now_jst.date()

    holiday_calendar = None
    if args.holiday_file:
        holiday_calendar = CsvHolidayCalendar.from_file(args.holiday_file)

    if not is_trading_day(d=d, holiday_calendar=holiday_calendar):
        logger.info("Non-trading day (%s); skipping (no notification).", d.isoformat())
        return 0

    try:
        hh, mm = args.min_time_jst.split(":", 1)
        min_dt = datetime(d.year, d.month, d.day, int(hh), int(mm), tzinfo=JST)
    except ValueError as exc:
        raise ValueError(f"Invalid --min-time-jst: {args.min_time_jst!r}") from exc

    deadline = now_jst + timedelta(minutes=int(args.max_wait_minutes))
    if now_jst < min_dt:
        logger.info(
            "Waiting until %s JST (deadline %s JST)",
            min_dt.strftime("%H:%M"),
            deadline.strftime("%H:%M"),
        )
        if not _sleep_until(min_dt, deadline=deadline):
            logger.error("Wait timeout before min-time; aborting.")
            _notify_failure(
                subject_prefix=args.subject_prefix,
                date_str=d.isoformat(),
                error="wait timeout",
            )
            return 1

    workdir = Path(args.workdir) if args.workdir else None
    if args.ready_check_cmd:
        ready_cmd = shlex.split(args.ready_check_cmd)
        logger.info("Waiting for readiness check: %s", ready_cmd)
        while True:
            now = datetime.now(timezone.utc).astimezone(JST)
            if now >= deadline:
                logger.error("Readiness check timeout; aborting.")
                _notify_failure(
                    subject_prefix=args.subject_prefix,
                    date_str=d.isoformat(),
                    error="readiness check timeout",
                )
                return 1
            check = _run_command(ready_cmd, cwd=workdir)
            if check.ok:
                logger.info("Ready.")
                break
            logger.info(
                "Not ready yet; retrying in %ss",
                max(5, int(args.ready_check_interval_seconds)),
            )
            time.sleep(max(5, int(args.ready_check_interval_seconds)))

    output_dir = Path(args.output_root) / d.isoformat()
    cmd = shlex.split(args.pipeline_cmd)

    logger.info("Running pipeline: %s", cmd)
    result = _run_command(cmd, cwd=workdir)
    if not result.ok:
        logger.error("Pipeline failed (exit=%s)", result.exit_code)
        _notify_failure(
            subject_prefix=args.subject_prefix,
            date_str=d.isoformat(),
            error=f"pipeline failed (exit={result.exit_code})\n\n{result.stdout_tail}",
        )
        return result.exit_code or 1

    report_path = output_dir / args.report_html
    if not report_path.exists():
        logger.error("Report file not found: %s", report_path)
        _notify_failure(
            subject_prefix=args.subject_prefix,
            date_str=d.isoformat(),
            error=f"missing {report_path}",
        )
        return 1

    report_html = report_path.read_text(encoding="utf-8")

    # The runner kit cannot infer these numbers; keep a sensible default shape.
    summary = DailyStockEmailSummary(
        date=d,
        regime=os.getenv("STOCK_ENGINE_REGIME", "(unknown)"),
        entry_candidates=int(os.getenv("STOCK_ENGINE_ENTRY_CANDIDATES", "0")),
        review_top_reasons=_split_env_list("STOCK_ENGINE_REVIEW_TOP"),
        diff_top=_split_env_list("STOCK_ENGINE_DIFF_TOP"),
        streak_days=int(os.getenv("STOCK_ENGINE_STREAK_DAYS", "0")),
        spotlight=os.getenv("STOCK_ENGINE_SPOTLIGHT", ""),
        improvement_hint=os.getenv("STOCK_ENGINE_IMPROVEMENT_HINT", ""),
        action_suggestions=_split_env_list("STOCK_ENGINE_ACTIONS"),
    )

    subject, text_body, html_body = build_stock_engine_success_email(
        subject_prefix=args.subject_prefix,
        summary=summary,
        report_html=report_html,
    )

    try:
        mailer = build_mailer(
            aws_region=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
            from_email=_require_env("FROM_EMAIL"),
            from_name=os.getenv("FROM_NAME", args.subject_prefix),
            to_email=_require_env("TO_EMAIL"),
        )
        logger.info("Using mail provider=%s", mailer.provider)
        mailer.send(subject, text_body, html_body)
    except (MailError, ValueError) as exc:
        # Keep analysis result; only the notification failed.
        logger.exception("Notification failed (kept outputs): %s", exc)
        return 0

    logger.info("Done.")
    return 0


def _split_env_list(name: str) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split("|") if p.strip()]


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ValueError(f"Environment variable {name} is required.")
    return value.strip()


def _notify_failure(*, subject_prefix: str, date_str: str, error: str) -> None:
    try:
        mailer = build_mailer(
            aws_region=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
            from_email=_require_env("FROM_EMAIL"),
            from_name=os.getenv("FROM_NAME", subject_prefix),
            to_email=_require_env("TO_EMAIL"),
        )
        subject = f"{subject_prefix} {date_str} 失敗"
        run_url = github_run_url()
        body = "パイプラインが失敗しました。\n\n"
        body += f"原因: {_truncate_text(error, max_chars=3000)}"
        if run_url:
            body += f"\n\nRunログ/再実行: {run_url}"
        mailer.send(subject, body)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send failure notification email.")


def _truncate_text(text: str, *, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 12)] + "\n... (truncated)"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
