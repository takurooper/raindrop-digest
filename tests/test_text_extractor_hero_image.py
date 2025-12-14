from __future__ import annotations

from raindrop_digest.text_extractor import _extract_hero_image_url


def test_extract_hero_image_url_prefers_og_image_and_resolves_relative():
    html_text = """
    <html><head>
      <meta property="og:image" content="/images/hero.png" />
    </head><body></body></html>
    """
    result = _extract_hero_image_url(html_text, "https://example.com/article")
    assert result == "https://example.com/images/hero.png"


def test_extract_hero_image_url_skips_tracking_pixels():
    html_text = """
    <html><head>
      <meta property="og:image" content="https://www.facebook.com/tr?id=1&ev=PageView" />
      <meta property="og:image" content="https://example.com/hero.jpg" />
    </head><body></body></html>
    """
    result = _extract_hero_image_url(html_text, "https://example.com/article")
    assert result == "https://example.com/hero.jpg"

