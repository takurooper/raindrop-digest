from __future__ import annotations

from raindrop_digest.runner_kit.html_email import extract_body_fragment


def test_extract_body_fragment_returns_body_contents() -> None:
    html = """
<!doctype html>
<html>
  <head><title>x</title></head>
  <body>
    <div>hello</div>
  </body>
</html>
"""
    assert extract_body_fragment(html) == "<div>hello</div>"


def test_extract_body_fragment_strips_script_tags() -> None:
    html = """
<html>
  <body>
    <script>alert('x');</script>
    <div>ok</div>
  </body>
</html>
"""
    assert "script" not in extract_body_fragment(html).lower()
    assert "<div>ok</div>" in extract_body_fragment(html)
