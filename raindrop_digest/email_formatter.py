from __future__ import annotations

from datetime import datetime
from typing import List, Tuple

from .config import BATCH_LOOKBACK_DAYS, JST, SUMMARY_CHAR_LIMIT
from .models import EmailContext, SummaryResult


def format_datetime_jst(dt: datetime) -> str:
    return dt.astimezone(JST).strftime("%Y-%m-%d %H:%M")


def build_email_subject(batch_date: datetime) -> str:
    date_str = batch_date.astimezone(JST).strftime("%Y-%m-%d")
    return f"【要約まとめ】{date_str} 直近{BATCH_LOOKBACK_DAYS}日版"


def build_email_body(batch_date: datetime, results: List[SummaryResult]) -> Tuple[str, str]:
    text_header = f"過去{BATCH_LOOKBACK_DAYS}日分のブックマークしたリンクの要約です。\n"
    html_parts = [
        """
<!doctype html>
<html>
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f7f8fb; color: #1c1d21; margin: 0; padding: 0; }}
  .container {{ max-width: 720px; margin: 0 auto; padding: 24px 16px 40px; }}
  .title {{ font-size: 20px; font-weight: 700; margin: 0 0 16px 0; }}
  .card {{ background: #ffffff; border-radius: 12px; padding: 16px 18px; margin: 0 0 16px 0; box-shadow: 0 8px 24px rgba(0,0,0,0.06); border: 1px solid #e6e8f0; }}
  .card h2 {{ margin: 0 0 8px 0; font-size: 16px; }}
  .meta {{ color: #5b6071; font-size: 13px; margin: 0 0 10px 0; }}
  .hero-img {{ width: 100%; max-width: 560px; height: auto; border-radius: 10px; display: block; margin: 12px auto 0; }}
  .summary {{ line-height: 1.6; font-size: 14px; color: #1f2430; }}
  .summary strong {{ color: #111; }}
  .footer {{ color: #7a7f92; font-size: 12px; margin-top: 24px; }}
  a {{ color: #2d6cdf; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
  <div class="container">
    <p class="title">過去{days}日分のブックマーク要約</p>
""".format(days=BATCH_LOOKBACK_DAYS)
    ]
    if not results:
        text_body = text_header + "\n今回は新着対象がありませんでした。"
        html_body = (
            html_parts[0]
            + '<div class="card"><div class="summary">今回は新着対象がありませんでした。</div></div>'
            + '<div class="footer">※ 各要約は最大{limit}文字目安で生成しています。</div></div></body></html>'.format(
                limit=SUMMARY_CHAR_LIMIT
            )
        )
        return text_body, html_body

    lines = [text_header]
    for idx, result in enumerate(results, start=1):
        item = result.item
        lines.append(f"{idx}. タイトル: {item.title}")
        lines.append(f"URL: {item.link}")
        lines.append(f"追加日時: {format_datetime_jst(item.created)}")
        lines.append("\n▼サマリー")
        if result.is_success() and result.summary:
            lines.append(result.summary.strip())
        else:
            lines.append("このURLは要約に失敗したので、手動確認してね。")
            if result.error:
                lines.append(f"(error: {result.error})")
        lines.append("")  # spacer

        html_parts.append('<div class="card">')
        html_parts.append(f"<h2>{idx}. {item.title}</h2>")
        html_parts.append(
            f'<p class="meta"><a href="{item.link}">こちらをクリック</a> ・ {format_datetime_jst(item.created)}</p>'
        )
        if result.hero_image_url:
            html_parts.append(
                f'<img class="hero-img" src="{result.hero_image_url}" alt="" '
                'style="width:100%;max-width:560px;height:auto;border-radius:10px;display:block;margin:12px auto 0;" />'
            )
        html_parts.append('<div class="summary"><strong>▼サマリー</strong><br>')
        if result.is_success() and result.summary:
            html_parts.append(result.summary.strip().replace("\n", "<br>"))
        else:
            failure_msg = "このURLは要約に失敗したので、手動確認してね。"
            if result.error:
                failure_msg += f"<br>(error: {result.error})"
            html_parts.append(failure_msg)
        html_parts.append("</div></div>")

    lines.append(f"\n※ 各要約は最大{SUMMARY_CHAR_LIMIT}文字目安で生成しています。")
    lines.append("改善の要望があればこちら(https://github.com/takurooper/raindrop_digest/issues)まで。")

    html_parts.append(f'<div class="footer">※ 各要約は最大{SUMMARY_CHAR_LIMIT}文字目安で生成しています。</div>')
    html_parts.append(
        '<div class="footer">改善の要望があれば<a href="https://github.com/takurooper/raindrop_digest/issues">こちら</a>まで。</div>'
    )
    html_parts.append("  </div></body></html>")

    return "\n".join(lines), "\n".join(html_parts)
