from __future__ import annotations

import pytest

from raindrop_digest.text_extractor import ExtractionError, detect_source, extract_text


@pytest.mark.parametrize(
    ("url", "expected_source"),
    [
        ("https://x.com/user/status/123", "x"),
        ("https://twitter.com/user/status/123", "x"),
        ("https://www.youtube.com/watch?v=abc", "youtube"),
        ("https://youtu.be/abc", "youtube"),
        (
            "https://speakerdeck.com/shibuiwilliam/puronputoyaezientowozi-dong-de-nizuo-rufang-fa",
            "speakerdeck",
        ),
    ],
)
def test_detect_source_unsupported(url: str, expected_source: str) -> None:
    assert detect_source(url) == expected_source


@pytest.mark.parametrize(
    ("url", "expected_error"),
    [
        (
            "https://x.com/user/status/123",
            "Xリンクは非対応です。対応を希望する場合は、開発者までご連絡ください。",
        ),
        (
            "https://www.youtube.com/watch?v=abc",
            "YouTubeリンクは非対応です。対応を希望する場合は、開発者までご連絡ください。",
        ),
        (
            "https://speakerdeck.com/shibuiwilliam/puronputoyaezientowozi-dong-de-nizuo-rufang-fa",
            "SpeakerDeckリンクは非対応です。対応を希望する場合は、開発者までご連絡ください。",
        ),
    ],
)
def test_extract_text_raises_for_unsupported_sources(url: str, expected_error: str) -> None:
    with pytest.raises(ExtractionError) as excinfo:
        extract_text(url)

    assert str(excinfo.value) == expected_error

