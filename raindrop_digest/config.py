from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta, timezone

JST = timezone(timedelta(hours=9))

# --------------------------------
# 設定値

# 何日前までのリンクを処理するか（日数）
BATCH_LOOKBACK_DAYS = 1

# 抽出する最大文字数
MAX_EXTRACT_CHARS = 10_000

# 要約の最大文字数
SUMMARY_CHAR_LIMIT = 600
IMAGE_TEXT_THRESHOLD = 1000
IMAGE_WORD_THRESHOLD = 500
MIN_IMAGES_FOR_SUMMARY = 3

DEFAULT_SYSTEM_PROMPT = """
You are a Japanese summarization bot.
Produce a concise summary within 500 characters.
Always respond in Japanese. If画像が渡される場合はその内容も考慮して要約する（本文から推測できない具体情報を補う程度でよい）。

# 要約ルール（全ジャンル共通）
- 論理的・簡潔・構造的にまとめること。
- 専門用語は可能な範囲で平易に言い換える。
- 主観・感想・推測は書かない。
- 最後まで一貫して日本語で答えること。

# 分野特化ルール（該当するとき必ず適用）
## ニュース記事
- 「何が起きたか」「なぜ起きたか」「今後どうなるか」を明確に記述する。

## 株・投資・経済記事
- 株価・指数・金利・為替（円安/円高）などの方向性を整理する。
- 今後のトレンド（上昇/下落の要因）を記事内容に基づき簡潔に述べる。
- 市場が注目するポイントとリスク要因をまとめる。
- 予測ではなく、あくまで記事内の事実・示唆に基づくこと。

## 技術記事
- 技術の目的、仕組み、利点、課題を4点セットで説明する。

## ビジネス／マーケティング記事
- 課題 → 解決策／戦略 → 効果 → 懸念点 の順に構造化して記述する。

# 出力フォーマット
1) 一行要約
2) 要点（箇条書き3〜6行）
""".strip()

# 画像付きリンクを要約するために必要な最小テキスト文字数
IMAGE_TEXT_THRESHOLD = 1000

# 画像付きリンクを要約するために必要な最小単語数（主に英語など非CJK）
IMAGE_WORD_THRESHOLD = 500

# 画像付きリンクを要約するために必要な最小画像枚数
MIN_IMAGES_FOR_SUMMARY = 3

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
    sendgrid_api_key: str | None
    brevo_api_key: str | None
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

        sendgrid_api_key = optional("SENDGRID_API_KEY")
        brevo_api_key = optional("BREVO_API_KEY")
        if brevo_api_key is None and sendgrid_api_key is None:
            raise ValueError("Either BREVO_API_KEY or SENDGRID_API_KEY is required.")

        return Settings(
            raindrop_token=require("RAINDROP_TOKEN"),
            openai_api_key=require("OPENAI_API_KEY"),
            sendgrid_api_key=sendgrid_api_key,
            brevo_api_key=brevo_api_key,
            to_email=require("TO_EMAIL"),
            from_email=require("FROM_EMAIL"),
            from_name=optional_with_default("FROM_NAME", from_name_default),
            openai_model=optional_with_default("OPENAI_MODEL", openai_model_default),
            summary_system_prompt=optional_with_default("SUMMARY_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
        )
