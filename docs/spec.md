# Raindrop要約メール配信サービス 仕様書

このドキュメントは「実装者（エンジニア）が挙動を理解する」ための仕様書です。利用者向けのセットアップ手順は `README.md` を参照してください。

## 1. システム全体像

### 1.1 使用技術

* **ストックサービス**: Raindrop.io
* **バッチ実行基盤**: GitHub Actions
* **アプリケーション言語**: Python
* **要約AI**: OpenAI API（Chat Completions / `gpt-4.1-mini` など）
* **メール送信**: AWS SES
* **本文抽出**: Python + HTML取得 + Readability系ライブラリ
  （例：`readability-lxml` または同等のテキスト抽出ロジック）

### 1.2 データフロー（概要）

1. ユーザがブラウザなどから **Raindropにリンクを保存**（未整理）。
2. 数日に1回、GitHub Actions が Python スクリプトを起動。
3. スクリプトが Raindrop API からアイテム一覧を取得。
4. `BATCH_LOOKBACK_DAYS` 日以内に追加され、かつ `確認済み` / `配信済み` / `要約失敗` タグが付いていないアイテムを抽出。
5. 各URLに対して HTML を取得し、本文テキストを抽出。

   * X / YouTube は現状「自動要約しない」扱い（手動確認）。
6. 抽出テキストを OpenAI API に渡し、日本語で要約を生成（プロンプトは `SUMMARY_SYSTEM_PROMPT` で上書き可能）。
7. 要約結果を集約してメール本文を構築し、AWS SES で自分宛に送信。
8. 送信に成功したアイテムに対し、Raindrop API で

   * 成功 → `note` に要約を保存＋タグ `配信済み` を付与
   * 失敗 → タグ `配信済み` + `要約失敗` を付与（note は空 or エラー内容）

---

## 2. 機能要件

### F-1. リンクストック

* ユーザは任意のブラウザ/アプリから、Raindrop にリンクを保存できる。
* 対象となるリンクの種類（MVPの取り扱い）：

  * 一般的なWebページのURL: 自動要約対象
  * X / YouTube: 手動確認（自動要約しない）

### F-2. 新着リンクの抽出

* バッチ処理時刻（JST）から **過去 `BATCH_LOOKBACK_DAYS` 日間**に `created` された Raindropアイテムを「新着」と定義する。
* 抽出対象アイテムは、以下すべてを満たすもの：

  1. `created >= (バッチ実行日時 - BATCH_LOOKBACK_DAYS日)`
  2. タグ `確認済み` / `配信済み` / `要約失敗` のいずれも付いていない

### F-3. 本文取得・要約

* 各アイテムについて、URLから本文テキストを取得する。

  * 通常のWebページ：

    * HTTP GET でHTMLを取得。
    * Readability系ライブラリまたは同等ロジックで本文テキストを抽出。
    * 抽出結果が極端に短い場合は `<title>` 要素なども補う。
  * X / YouTube：

    * 現状は自動要約しない（要約失敗としてメールに掲載し、手動確認を促す）。
    * 将来的に対応する場合は別途設計する。
* OpenAI API へ渡すプロンプト仕様：

  * **出力言語は常に日本語**。
  * **1件あたり最大500文字**程度になるよう制限。
  * プロンプトは `SUMMARY_SYSTEM_PROMPT`（Secret/Env）で上書きできる。未設定時はコード内のデフォルトが使われる。
  * 出力構成（デフォルト例）：

    1. 一行要約
    2. 内容の要点（箇条書き or 2〜3行）
    3. 自分用メモ/キーワード

* 見出し画像（OG/Twitter card）を別途抽出し、メール本文に表示する（OpenAI への入力とは独立）。

### F-4. メール生成・送信

* 対象アイテムを1通のメールにまとめて送信する。

* メール件名フォーマット：

  * `【要約まとめ】YYYY-MM-DD 直近{BATCH_LOOKBACK_DAYS}日版`

    * `YYYY-MM-DD` は **バッチ実行日の JST** 日付。

* メール本文：

* プレーンテキスト + HTML の両方を送信する（SES の Text/Html）。
  * HTML 側はカードレイアウトで、各記事に見出し画像（取得できる場合）を挿入する。

  ```text
  過去{BATCH_LOOKBACK_DAYS}日分のブックマークしたリンクの要約です。

  ====================
  1. タイトル: {Raindropアイテムのtitle}
  URL: {link}
  追加日時: {Raindropのcreated（JSTに変換して表示）}
  {本文が1000文字未満のときは注意文を1行追加}

  ▼サマリー
  {GPTが生成した要約}

  ====================
  2. タイトル: ...
  ...
  ```

* 要約に失敗したURLについては、以下のように表示する：

  ```text
  ====================
  N. タイトル: {Raindropアイテムのtitle}
  URL: {link}
  追加日時: {created}

  ▼サマリー
  このURLは要約に失敗したので、手動確認してね。
  ```

* 宛先メールアドレスは事前設定（環境変数/Secrets）で指定。

### F-5. Raindropへの書き戻し

* 要約成功時：

  * 対象アイテムの `note` フィールドに、日本語要約テキストを保存する。

    * 既存の note は保持せず、最新の要約で上書きする。
  * 対象アイテムにタグ `配信済み` を追加する。
* 要約失敗時：

  * `note` は空のまま or 簡易的なエラーメッセージ（実装側で判断）。
  * タグ `配信済み` および `要約失敗` を追加する。

* 送信失敗時：

* SES 送信が最終的に失敗した場合、Raindropへの note/tag 更新は行わない（配信済み扱いにしない）。

---

## 3. 非機能要件

* **バッチ実行頻度**: 数日に1回
* **実行時間帯**: 任意

  * GitHub Actions の cron は UTC。
* **1件あたり要約長**: 最大500文字程度
* **メール1通あたり件数上限**: なし（新着対象はすべて掲載）
* **応答時間**: バッチ完了まで数分以内（実用上問題ない範囲なら許容）
* **可用性**: 個人ユースのため、たまの失敗は許容。
  失敗時は翌バッチまでに手動再実行可能な構成とする。

---

## 4. Raindrop 運用仕様

### 4.1 タグ運用

* `確認済み`

  * ユーザが「自分で内容を確認した」アイテムにつける任意タグ。
  * このタグがあるアイテムはバッチ対象外。
* `配信済み`

  * バッチ処理が **メール送信を完了した** アイテムに自動付与。
* `要約失敗`

  * 要約処理が失敗したアイテムに自動付与。
  * メールには「要約失敗」として掲載するが、次回以降の対象からは除外。

※ タグ名は日本語固定。仕様上、コード内ではそれぞれのタグ名を **文字列定数** として扱う。

### 6.2 Note運用

* 要約成功時、アイテムの `note` に要約テキストを保存。
* Noteは、RaindropのUI上からも閲覧可能な状態を想定。

---

## 5. バッチ処理詳細設計

### 5.1 実行タイミング

* GitHub Actions の `schedule` トリガーを使用。
* JST 06:00 に相当するUTC時刻は前日21:00。
* cron 例：`0 21 */3 * *`

### 5.2 処理アルゴリズム（擬似コード）

```pseudo
main():
    now_utc = current_utc_datetime()
    now_jst = utc_to_jst(now_utc)
    threshold = now_jst - 3 days

    items = fetch_raindrop_items

    targets = []
    for item in items:
        if item.created < threshold:
            continue
        if has_tag(item, "確認済み") or has_tag(item, "配信済み") or has_tag(item, "要約失敗"):
            continue
        targets.append(item)

    results = []
    for item in targets:
        try:
            raw_text = extract_text(item.link)
            if not raw_text:
                raise ExtractError

            summary = summarize_with_openai(raw_text)
            results.append({ item, summary, status: "success" })
        except Exception as e:
            results.append({ item, summary: None, status: "failed", error: e })

    email_body = build_email_body(now_jst.date(), results)

    send_email_via_ses(subject, email_body)

    for r in results:
        if r.status == "success":
            update_raindrop_note(r.item.id, r.summary)
            add_raindrop_tags(r.item.id, ["配信済み"])
        else:
            add_raindrop_tags(r.item.id, ["配信済み", "要約失敗"])
```

---

## 6. 外部API仕様（利用範囲）

※ 正確なエンドポイントパスやパラメータは実装時に公式ドキュメントを参照する。ここでは「どの種類の操作を行うか」を規定する。

### 6.1 Raindrop API

* 認証: API Token（Bearer）
* 利用する操作：

  1. **コレクション内アイテム一覧取得**

     * `GET /raindrops/{collectionId}`
     * パラメータ：

       * `perpage`: 取得件数（例: 100）
       * `page`: ページ番号
       * `sort`: `-created` など
     * 取得フィールド：

       * `id`
       * `link`
       * `title`
       * `created`
       * `tags`
       * `note`
  2. **アイテム更新（note・タグ付与）**

     * `PUT /raindrop/{id}`
     * ボディ例：

       ```json
       {
         "note": "ここに要約テキスト",
         "tags": ["配信済み", "既存タグ..."]
       }
       ```

### 7.2 OpenAI API（Chat Completions）

* エンドポイント: `POST /v1/chat/completions`
* 使用モデル: `gpt-4.1-mini`（想定）
* 入力：

  * `messages`:

    * `system`: 日本語の要約ボットとしての振る舞い指示、出力形式、500文字制限を明示。
    * `user`: 抽出した本文テキスト（長すぎる場合は先頭数千文字にトリム）。
* 出力：

  * `choices[0].message.content` を要約テキストとして使用。

### 7.3 AWS SES（メール送信）

* エンドポイント: `SendEmail`（SESv2）
* 認証: GitHub Actions OIDC + IAM Role（`aws-actions/configure-aws-credentials`）

---

## 8. 実装構成（現在）

### 8.1 リポジトリ構成（現状）

```text
.
├── .github
│   └── workflows
│       └── schedule_run.yml         # GitHub Actions ワークフロー定義
├── main.py                          # エントリポイント
├── raindrop_digest
│   ├── config.py                    # 定数・環境変数読み込み
│   ├── raindrop_client.py           # Raindrop API ラッパ
│   ├── text_extractor.py            # HTML取得 + 本文抽出 + 見出し画像抽出
│   ├── summarizer.py                # OpenAI 要約ロジック
│   ├── email_formatter.py           # メール本文生成（HTML + テキスト）
│   ├── mailer.py                    # AWS SES メール送信
│   └── utils.py                     # URL正規化など共通処理
└── tests
```

### 8.2 設定値（環境変数）

* Secrets（機密）:

  * `RAINDROP_TOKEN`
  * `OPENAI_API_KEY`
  * `AWS_ROLE_ARN`
  * （任意）`SUMMARY_SYSTEM_PROMPT`

※ AWSリージョン（`AWS_REGION`）は GitHub Actions の `aws-actions/configure-aws-credentials` により環境変数として注入される前提です。
* Variables（機密でない）:

  * `TO_EMAIL`
  * `FROM_EMAIL`
  * `FROM_NAME`
  * （任意）`OPENAI_MODEL`
  * （任意）`BATCH_LOOKBACK_DAYS`（未設定なら `1`）

### 8.3 GitHub Actions Variables（機密でないもの）

* `TO_EMAIL` 宛先メールアドレス
* `FROM_EMAIL` 送信元メールアドレス
* `FROM_NAME` 送信元表示名（例: `Raindrop要約メール配信サービス`）
* （任意）`OPENAI_MODEL` 使用モデル名（デフォルト `gpt-4.1-mini`）
* （任意）`BATCH_LOOKBACK_DAYS` バッチで対象とする過去日数（デフォルト `1`）

### 8.4 ローカル開発セットアップ

1. Python 3.11 以上を準備（推奨）
2. [uv](https://docs.astral.sh/uv/) をインストール
3. 依存インストール

   ```bash
   uv sync
   ```

4. 必要な環境変数をセット（ローカルでは `.env` やシェルで設定）

   ```bash
   export RAINDROP_TOKEN=...
   export OPENAI_API_KEY=...
   export AWS_REGION=ap-northeast-1
   export SUMMARY_SYSTEM_PROMPT="（必要に応じてカスタムプロンプトをここに書く）"
   export TO_EMAIL=...
   export FROM_EMAIL=...
   export FROM_NAME="Raindrop要約メール配信サービス"
   export OPENAI_MODEL="gpt-4.1-mini"
   export BATCH_LOOKBACK_DAYS=1
   ```

5. 実行

   ```bash
   uv run python main.py
   ```

6. テスト

   ```bash
   uv run pytest
   ```

### 8.5 プロンプト編集

* 要約プロンプトは GitHub Actions Secret `SUMMARY_SYSTEM_PROMPT` またはローカル環境変数 `SUMMARY_SYSTEM_PROMPT` で上書きする。
* 未設定時はコード内のデフォルトプロンプト（約500文字制限を含む）が使われる。

---

## 10. エラー処理・リトライ方針（実装準拠）

### 10.1 個別URLの要約失敗

* 失敗条件例：

  * タイムアウト・HTTPエラー
  * 本文抽出結果が空
  * OpenAI API エラー
* 対応：

  * メール本文では「要約失敗」として表示。
  * Raindropアイテムにはタグ `配信済み` と `要約失敗` を付与。
  * `note` は空 or エラーメッセージ（実装時判断）。
  * 個別の失敗はバッチ全体を止めない（GAは成功扱いのまま）。

### 10.2 全体処理・メール送信失敗

* SES への送信が失敗した場合：

  * 502/503/504 は 1 回リトライする。
  * リトライ後も失敗した場合は、メール送信を諦めて処理を継続する（ただし Raindrop への note/tag 更新は行わない）。
  * GitHub Actions のログにエラーを出力する。

### 10.3 レート制限等

* OpenAI / Raindrop / SES のレート制限に達した場合：

  * 502/503/504 のみ 1 回リトライする（それ以外は個別失敗扱い）。
  * 個別URLの要約失敗は処理継続し、メールには「手動確認」として掲載する。
  * バッチ終了時に Total/Success/Failure をログ出力する。
  * Exit code は「対象が 1 件以上あり、かつ全件失敗」のときのみ 1。1 件でも成功があれば 0。

### 10.5 実装との差分・補足

* X / YouTube リンクは自動要約せず「要約失敗（手動確認）」として扱う。
* 見出し画像（OG/Twitterカード）を抽出し、メールのカードに表示する。
* 本文が1000文字未満のとき、メール本文に「この記事は文字数が1000未満のため、情報量が不足している可能性があります。」を追記する。
* メールはプレーンテキスト＋HTML（カード風デザイン）で送信される。
* ログは GA 標準出力に詳細を出し、各リンク処理ごとに区切って記録する。

### 10.4 ログ出力

* 出力先：標準出力（GitHub Actions のログに記録される）。
* 主要内容：

  * Raindrop の取得件数・処理対象件数。
  * 各 URL の取得開始ログと、抽出後の文字数。
  * 要約・メール送信・Raindrop 更新の成功/失敗。
  * 失敗時の例外メッセージ（HTTP エラーや要約 API エラーなど）。
* 秘匿情報について：

  * API トークンやキーはログに出力しない。ログに含まれるのは URL、件数、処理結果、例外概要のみ。

---

## 11. テスト観点（簡易）

* 単体テストレベル：

  * URL種別判定ロジック（YouTube判定 / 通常ページ）
  * HTMLから本文抽出処理（いくつかの実際のページでの挙動確認）
  * OpenAIからのサマリを500文字以内に収めるロジック
  * メール本文フォーマットの整形
* 結合テスト：

  * テスト用の Raindrop コレクションを用意し、2〜3件のテストデータを保存。
  * GitHub Actions の `workflow_dispatch` から手動実行し、

    * メール内容
    * RaindropのNote・タグ
      を確認する。

---

## 12. 今後の拡張アイデア（非スコープ）

* YouTube Data API を利用した字幕取得・要約、コメント取得・要約。
* Xポストのリツイート、返信の取得・インプレゾンビの除外、要約
* メール本文のHTML化（リンク・段落見やすく整形）。
* 「優先度」タグを導入し、重要度に応じてメール内の並び順を変える。
* 週次/月次のハイライトメール機能（よく出てきたキーワードランキングなど）。
* メール通知の他に、LINE宛に送信する機能。
