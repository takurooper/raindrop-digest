# runner_kit

GitHub Actions で「日次バッチ実行 + メール通知」を作るための共通部品を 1 つにまとめたディレクトリです。

他プロジェクトに持っていくときは、この `raindrop_digest/runner_kit/` を丸ごとコピーして使う想定です。

## 何が入っているか

- `mailer.py`
  - AWS SES の送信クライアント（2回だけリトライ）
  - `AWS_REGION` を使って SES を送信

- `stock_engine_email.py`
  - `report.html` を本文に埋め込む「日次レポート通知」テンプレート（text fallback 同梱）

- `pipeline_runner.py`
  - 東証取引日（週末 + 休日ファイル）判定
  - JST 指定の「実行開始時刻まで待機」
  - 任意の `--ready-check-cmd` をリトライして「データ反映待ち」（例: yfinance）
  - パイプライン実行 → レポート読み込み → メール送信
  - 通知失敗でも分析結果（output）は残す（exit 0）

- `workflows/stock_engine_daily.yml`
  - GitHub Actions のスケジュール実行テンプレ
  - 生成物 `output/**` を artifact として残す（成功/失敗問わず）

- `raindrop_email_formatter.py`
  - このリポジトリ（raindrop-digest）用の既存メール本文生成を移したもの
  - 他プロジェクトにコピーするときは不要なら削除してOK

## 使い方（stock-engine 例）

1) 他プロジェクトに `raindrop_digest/runner_kit/` をコピー

2) workflow に `python -m ...pipeline_runner` を組み込む

3) Secrets / Variables

- Secrets:
  - `AWS_REGION`
  - （任意）`AWS_ACCESS_KEY_ID`
  - （任意）`AWS_SECRET_ACCESS_KEY`
  - （任意）`AWS_SESSION_TOKEN`
- Variables:
  - `TO_EMAIL`, `FROM_EMAIL`, `FROM_NAME`

任意で、メール上部の「1分で判断できる要約」を env で渡せます。

- `STOCK_ENGINE_REGIME`
- `STOCK_ENGINE_ENTRY_CANDIDATES`
- `STOCK_ENGINE_REVIEW_TOP`（`|` 区切り）
- `STOCK_ENGINE_DIFF_TOP`（`|` 区切り）
- `STOCK_ENGINE_STREAK_DAYS`
- `STOCK_ENGINE_SPOTLIGHT`
- `STOCK_ENGINE_IMPROVEMENT_HINT`
- `STOCK_ENGINE_ACTIONS`（`|` 区切り）

## 東証取引日（休日）の扱い

`pipeline_runner.py` はデフォルトで「土日スキップ」のみです。

祝日/取引所休場を正確にスキップしたい場合は `--holiday-file` を指定してください。
ファイル形式は `YYYY-MM-DD` を 1 行 1 日（コメント `#` 可）です。
