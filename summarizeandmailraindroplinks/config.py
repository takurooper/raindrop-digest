from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta, timezone

JST = timezone(timedelta(hours=9))

# --------------------------------
# 設定値

# 何日前までのリンクを処理するか（日数）
BATCH_LOOKBACK_DAYS = 3

# 抽出する最大文字数
MAX_EXTRACT_CHARS = 10_000

# 要約の最大文字数
SUMMARY_CHAR_LIMIT = 500

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
    sendgrid_api_key: str
    to_email: str
    from_email: str
    from_name: str
    openai_model: str = "gpt-4.1-mini"

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

        return Settings(
            raindrop_token=require("RAINDROP_TOKEN"),
            openai_api_key=require("OPENAI_API_KEY"),
            sendgrid_api_key=require("SENDGRID_API_KEY"),
            to_email=require("TO_EMAIL"),
            from_email=require("FROM_EMAIL"),
            from_name=optional_with_default("FROM_NAME", from_name_default),
            openai_model=optional_with_default("OPENAI_MODEL", openai_model_default),
        )
