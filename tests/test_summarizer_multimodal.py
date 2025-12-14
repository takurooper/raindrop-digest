from __future__ import annotations

from typing import Any, List

from raindrop_digest.summarizer import Summarizer


class FakeOpenAI:
    def __init__(self):
        self.last_messages: List[Any] | None = None
        self.chat = self.Chat(self)

    class Chat:
        def __init__(self, outer: "FakeOpenAI"):
            self.completions = outer.Completions(outer)

    class Completions:
        def __init__(self, outer: "FakeOpenAI"):
            self._outer = outer

        def create(self, model, messages, temperature):
            self._outer.last_messages = messages

            class Choice:
                def __init__(self):
                    self.message = type("msg", (), {"content": "dummy"})

            class Response:
                def __init__(self):
                    self.choices = [Choice()]

            return Response()


def test_include_images_when_short_text_and_many_images():
    fake_client = FakeOpenAI()
    s = Summarizer(api_key="dummy", model="gpt-4.1-mini", client=fake_client)
    s.summarize("短いテキスト", ["img1", "img2", "img3"])
    user_content = fake_client.last_messages[1]["content"]  # type: ignore[index]
    assert any(part.get("type") == "image_url" for part in user_content)


def test_openai_retry_on_503():
    class E(Exception):
        def __init__(self):
            self.status_code = 503

    class FlakyOpenAI(FakeOpenAI):
        def __init__(self):
            super().__init__()
            self.calls = 0
            self.chat = self.Chat(self)

        class Completions(FakeOpenAI.Completions):
            def create(self, model, messages, temperature):
                self._outer.calls += 1
                if self._outer.calls == 1:
                    raise E()
                return super().create(model, messages, temperature)

    fake_client = FlakyOpenAI()
    s = Summarizer(api_key="dummy", model="gpt-4.1-mini", client=fake_client)
    assert s.summarize("短いテキスト", ["img1", "img2", "img3"]) == "dummy"


def test_text_only_when_insufficient_images():
    fake_client = FakeOpenAI()
    s = Summarizer(api_key="dummy", model="gpt-4.1-mini", client=fake_client)
    s.summarize("短いテキスト", ["img1"])
    user_content = fake_client.last_messages[1]["content"]  # type: ignore[index]
    assert all(part.get("type") == "text" for part in user_content)


def test_text_only_when_long_text():
    fake_client = FakeOpenAI()
    s = Summarizer(api_key="dummy", model="gpt-4.1-mini", client=fake_client)
    long_text = "長" * 1200  # exceeds IMAGE_TEXT_THRESHOLD to force text-only
    s.summarize(long_text, ["img1", "img2", "img3", "img4"])
    user_content = fake_client.last_messages[1]["content"]  # type: ignore[index]
    assert all(part.get("type") == "text" for part in user_content)


def test_text_only_when_english_exceeds_word_threshold():
    fake_client = FakeOpenAI()
    s = Summarizer(api_key="dummy", model="gpt-4.1-mini", client=fake_client)
    long_english = ("word " * 600).strip()
    s.summarize(long_english, ["img1", "img2", "img3"])
    user_content = fake_client.last_messages[1]["content"]  # type: ignore[index]
    assert all(part.get("type") == "text" for part in user_content)


def test_include_images_when_english_within_word_threshold():
    fake_client = FakeOpenAI()
    s = Summarizer(api_key="dummy", model="gpt-4.1-mini", client=fake_client)
    short_english = ("word " * 400).strip()
    s.summarize(short_english, ["img1", "img2", "img3"])
    user_content = fake_client.last_messages[1]["content"]  # type: ignore[index]
    assert any(part.get("type") == "image_url" for part in user_content)
