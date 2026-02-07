from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .gha import github_run_url
from .html_email import extract_body_fragment, wrap_in_email_shell


@dataclass(frozen=True)
class DailyStockEmailSummary:
    date: date
    regime: str
    entry_candidates: int
    review_top_reasons: list[str]
    diff_top: list[str]
    streak_days: int
    spotlight: str
    improvement_hint: str
    action_suggestions: list[str]


def build_stock_engine_success_email(
    *,
    subject_prefix: str,
    summary: DailyStockEmailSummary,
    report_html: str,
    env: dict[str, str] | None = None,
) -> tuple[str, str, str]:
    """Return (subject, text_body, html_body)."""

    date_str = summary.date.isoformat()
    run_url = github_run_url(env)
    subject = f"{subject_prefix} {date_str} 完了"

    text_lines: list[str] = []
    text_lines.append(f"{subject_prefix} {date_str}")
    text_lines.append("")
    text_lines.append("1分で判断できる要約")
    text_lines.append(f"- レジーム: {summary.regime}")
    text_lines.append(f"- Entry候補数: {summary.entry_candidates}")
    if summary.review_top_reasons:
        text_lines.append(
            "- 注意点(Top): " + " / ".join(summary.review_top_reasons[:3])
        )
    if summary.diff_top:
        text_lines.append("- 昨日との差分(Top): " + " / ".join(summary.diff_top[:3]))
    text_lines.append("")
    text_lines.append("見たくなる仕掛け")
    text_lines.append(f"- 連続実行日数: {summary.streak_days}")
    if summary.spotlight:
        text_lines.append(f"- 今日の注目: {summary.spotlight}")
    if summary.improvement_hint:
        text_lines.append(f"- 改善の余地: {summary.improvement_hint}")
    if summary.action_suggestions:
        text_lines.append(
            "- 手動アクション提案: " + " / ".join(summary.action_suggestions[:3])
        )
    if run_url:
        text_lines.append("")
        text_lines.append(f"Run: {run_url}")
    text_lines.append("")
    text_lines.append("---- report.html ----")
    text_lines.append("(HTML版にレポートを埋め込んでいます)")
    text_body = "\n".join(text_lines)

    header_html = _header_html(
        subject_prefix=subject_prefix,
        date_str=date_str,
        run_url=run_url,
        summary=summary,
    )
    embedded = extract_body_fragment(report_html)
    body_html = (
        '<div style="font-size:14px;line-height:1.65;color:#111827;">'
        '<div style="margin:0 0 14px 0;color:#374151;">下に当日レポートを埋め込んでいます。</div>'
        '<div style="border:1px solid #eef0f6;border-radius:12px;overflow:hidden;">'
        f"{embedded}"
        "</div>"
        "</div>"
    )
    html_body = wrap_in_email_shell(
        title=subject, header_html=header_html, body_html=body_html
    )
    return subject, text_body, html_body


def _header_html(
    *,
    subject_prefix: str,
    date_str: str,
    run_url: str | None,
    summary: DailyStockEmailSummary,
) -> str:
    def chips(lines: Iterable[str]) -> str:
        parts: list[str] = []
        for s in lines:
            if not s:
                continue
            parts.append(
                '<span style="display:inline-block;margin:6px 8px 0 0;padding:6px 10px;'
                "border:1px solid #e6e8f0;border-radius:999px;background:#ffffff;"
                'font-size:12px;color:#374151;">' + _escape_html(s) + "</span>"
            )
        return "".join(parts)

    top = (
        f'<div style="font-weight:800;font-size:16px;letter-spacing:0.2px;">{_escape_html(subject_prefix)} {date_str}</div>'
        f'<div style="margin-top:6px;color:#4b5563;font-size:13px;">'
        f'レジーム: <strong style="color:#111827;">{_escape_html(summary.regime)}</strong>'
        f' / Entry候補: <strong style="color:#111827;">{summary.entry_candidates}</strong>'
        "</div>"
    )

    aux: list[str] = []
    aux.append(f"連続実行 {summary.streak_days}日")
    if summary.review_top_reasons:
        aux.append("REVIEW: " + ", ".join(summary.review_top_reasons[:3]))
    if summary.diff_top:
        aux.append("昨日差分: " + ", ".join(summary.diff_top[:2]))

    link_html = ""
    if run_url:
        link_html = (
            '<div style="margin-top:10px;font-size:12px;">'
            f'<a href="{_escape_attr(run_url)}" style="color:#2563eb;text-decoration:none;">Runログ / 再実行導線</a>'
            "</div>"
        )

    return top + chips(aux) + link_html


def _escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_attr(s: str) -> str:
    return _escape_html(s).replace('"', "&quot;")
