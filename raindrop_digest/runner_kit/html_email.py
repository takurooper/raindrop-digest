from __future__ import annotations

import re


_BODY_RE = re.compile(
    r"<body[^>]*>(?P<body>.*)</body>", flags=re.IGNORECASE | re.DOTALL
)
_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", flags=re.IGNORECASE | re.DOTALL)


def extract_body_fragment(html: str) -> str:
    """Extract a <body> fragment when present; otherwise return the input.

    This is meant for embedding an existing report.html into a larger email HTML.
    """

    cleaned = _SCRIPT_RE.sub("", html)
    match = _BODY_RE.search(cleaned)
    if not match:
        return cleaned
    return match.group("body").strip()


def wrap_in_email_shell(*, title: str, header_html: str, body_html: str) -> str:
    """Build a single HTML document with conservative inline-first styles."""

    return (
        """<!doctype html>
<html>
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>{title}</title>
</head>
<body style=\"margin:0;padding:0;background:#f7f8fb;color:#14161b;\">
  <div style=\"max-width:860px;margin:0 auto;padding:22px 14px 40px;\">
    <div style=\"background:#ffffff;border:1px solid #e6e8f0;border-radius:14px;box-shadow:0 10px 30px rgba(0,0,0,0.06);overflow:hidden;\">
      <div style=\"padding:16px 18px;border-bottom:1px solid #eef0f6;background:linear-gradient(180deg,#fbfcff, #ffffff);\">
        {header}
      </div>
      <div style=\"padding:18px 18px 20px;\">
        {body}
      </div>
    </div>
    <div style=\"margin-top:14px;color:#6b7280;font-size:12px;line-height:1.5;\">このメールは自動送信です。</div>
  </div>
</body>
</html>"""
    ).format(title=_escape_title(title), header=header_html, body=body_html)


def _escape_title(title: str) -> str:
    return (
        title.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
