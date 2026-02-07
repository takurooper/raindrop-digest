from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta, timezone

JST = timezone(timedelta(hours=9))


def _env_int(name: str, default: int, *, min_value: int | None = None) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default

    try:
        parsed = int(raw_value.strip())
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {name} must be an integer, got {raw_value!r}."
        ) from exc

    if min_value is not None and parsed < min_value:
        raise ValueError(
            f"Environment variable {name} must be >= {min_value}, got {parsed}."
        )

    return parsed


# --------------------------------
# 設定値

# 何日前までのリンクを処理するか（日数）
BATCH_LOOKBACK_DAYS = _env_int("BATCH_LOOKBACK_DAYS", default=1, min_value=1)

# 抽出する最大文字数
MAX_EXTRACT_CHARS = 10_000

# 要約の最大文字数
SUMMARY_CHAR_LIMIT = 500

# 本文が短い記事への注意文を入れる閾値（文字数）
SHORT_ARTICLE_CHAR_THRESHOLD = 1000

DEFAULT_SYSTEM_PROMPT = """
You are a Japanese summarization bot.
Produce a concise summary within 500 characters.
Always respond in Japanese.

# 要約ルール（全ジャンル共通）
- 論理的・簡潔・構造的にまとめること。
- 専門用語は可能な範囲で平易に言い換える。
- 主観・感想・推測は書かない。
- 最後まで一貫して日本語で答えること。

# 出力フォーマット
1) 一行要約
2) 要点（箇条書き3〜6行）
""".strip()

# Raindrop.io のタグ
TAG_CONFIRMED = "確認済み"
TAG_DELIVERED = "配信済み"
TAG_FAILED = "要約失敗"

# Raindrop API の未整理コレクションID
UNSORTED_COLLECTION_ID = -1
# --------------------------------


@dataclass
class Settings:
    raindrop_token: str
    openai_api_key: str
    aws_region: str
    aws_access_key_id: str | None
    aws_secret_access_key: str | None
    aws_session_token: str | None
    to_email: str
    from_email: str
    from_name: str
    openai_model: str = "gpt-4.1-mini"
    summary_system_prompt: str = DEFAULT_SYSTEM_PROMPT

    @staticmethod
    def from_env(
        openai_model_default: str = "gpt-4.1-mini",
        from_name_default: str = "Raindrop要約メール配信サービス",
    ) -> "Settings":
        def require(name: str) -> str:
            value = os.getenv(name)
            if value is None or not value.strip():
                raise ValueError(f"Environment variable {name} is required.")
            return value

        def optional_with_default(name: str, default: str) -> str:
            value = os.getenv(name)
            if value is None or not value.strip():
                return default
            return value.strip()

        def optional(name: str) -> str | None:
            value = os.getenv(name)
            if value is None or not value.strip():
                return None
            return value.strip()

        aws_region = optional("AWS_REGION") or optional("AWS_DEFAULT_REGION")
        if aws_region is None:
            raise ValueError("AWS_REGION or AWS_DEFAULT_REGION is required.")

        return Settings(
            raindrop_token=require("RAINDROP_TOKEN"),
            openai_api_key=require("OPENAI_API_KEY"),
            aws_region=aws_region,
            aws_access_key_id=optional("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=optional("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=optional("AWS_SESSION_TOKEN"),
            to_email=require("TO_EMAIL"),
            from_email=require("FROM_EMAIL"),
            from_name=optional_with_default("FROM_NAME", from_name_default),
            openai_model=optional_with_default("OPENAI_MODEL", openai_model_default),
            summary_system_prompt=optional_with_default(
                "SUMMARY_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT
            ),
        )
