# Raindrop要約メール配信サービス 仕様書

## 1. プロジェクト概要

### 1.1 目的

* X や Webなどで見つけた「あとで読みたい」リンクを **Raindrop.io の一箇所にストック**し、
* **3日に一度のバッチ処理**でまとめて要約し、
* **メールで日本語のサマリを受け取れる**ようにする。

これにより、「その場その場で ChatGPT に投げる」のではなく、「あとで読みたいものを貯めて、朝にダイジェストを受け取る」ワークフローを実現する。

### 1.2 スコープ（今回のMVP）

* ストック先は **Raindrop.io 。コレクションなどに特に整理する必要なく、「未整理」のままで良い。
* 要約対象は Xのポスト、Xのポストに添付されたWeb記事全般やYouTubeリンク、あるいはWeb記事全般やYouTubeリンクそのもの。
* 要約処理は **OpenAI API（gpt-4.1-mini想定）** にて実行。
* メール配信は **SendGrid** 経由。
* バッチ処理実行環境は **GitHub Actions**（以降 GA）＋ **Pythonスクリプト**。

---

## 2. 用語定義

* **Raindrop**
  ブックマーク管理サービス。以降「Raindrop」と記載した場合、Raindrop.io を指す。

* **タグ**

  * `確認済み`
    ユーザが「内容を自分で確認済み」と判断したものに手動で付与する想定。
    → このタグが付いているアイテムは、要約バッチの対象外。
  * `配信済み`
    バッチ処理により「メールに掲載済み」のアイテムに自動付与。
    → 次回以降のバッチでは対象外。
  * `要約失敗`
    何らかの理由で要約処理が失敗したアイテムに自動付与。
    → 次回以降のバッチでは対象外（メールには「要約失敗」として掲載）。

* **Note**
  Raindropアイテムに紐づくメモ欄。要約テキストを書き戻す。

---

## 3. システム全体像

### 3.1 使用技術

* **ストックサービス**: Raindrop.io
* **バッチ実行基盤**: GitHub Actions
* **アプリケーション言語**: Python
* **要約AI**: OpenAI API（Chat Completions / gpt-4.1-mini想定）
* **メール送信**: SendGrid API
* **本文抽出**: Python + HTML取得 + Readability系ライブラリ
  （例：`readability-lxml` または同等のテキスト抽出ロジック）

### 3.2 データフロー（概要）

1. ユーザが X / Safari などから **Raindropにリンクを保存**。
2. 3日に1回、GitHub Actions が Python スクリプトを起動。
3. スクリプトが Raindrop API からアイテム一覧を取得。
4. 直近3日以内に追加され、かつ `確認済み` / `配信済み` / `要約失敗` タグが付いていないアイテムを抽出。
5. 各URLに対して HTML を取得し、本文テキストを抽出。

   * YouTube URLの場合はタイトル＋説明文を取得。
6. 抽出テキストを OpenAI API に渡し、日本語で最大500文字の要約＋自分用メモ/キーワードを生成。
7. 要約結果を集約してメール本文を構築し、SendGrid API で自分宛に送信。
8. 送信に成功したアイテムに対し、Raindrop API で

   * 成功 → `note` に要約を保存＋タグ `配信済み` を付与
   * 失敗 → タグ `配信済み` + `要約失敗` を付与（note は空 or エラー内容）

---

## 4. 機能要件

### F-1. リンクストック

* ユーザは任意のブラウザ/アプリから、Raindrop にリンクを保存できる。
* 対象となるリンクの種類：

  * XポストのURL
  * 一般的なWebページのURL
  * YouTube動画のURL

### F-2. 新着リンクの抽出

* バッチ処理時刻（JST）から **過去3日間**に `created` された Raindropアイテムを「新着」と定義する。
* 抽出対象アイテムは、以下すべてを満たすもの：

  1. `created >= (バッチ実行日時 - 3日)`
  2. タグ `確認済み` / `配信済み` / `要約失敗` のいずれも付いていない

### F-3. 本文取得・要約

* 各アイテムについて、URLから本文テキストを取得する。

  * 通常のWebページ：

    * HTTP GET でHTMLを取得。
    * Readability系ライブラリまたは同等ロジックで本文テキストを抽出。
    * 抽出結果が極端に短い場合は `<title>` 要素なども補う。
  * YouTube：

    * URLのホスト名が `youtube.com` または `youtu.be` の場合、YouTubeと判定。
    * ページHTMLから `<title>` および `meta[name="description"]` の内容を抽出。
    * 抽出した `タイトル + 説明文` を要約対象テキストとする。
* OpenAI API へ渡すプロンプト仕様：

  * **出力言語は常に日本語**。
  * **1件あたり最大500文字**程度になるよう制限。
  * 出力構成（例）：

    1. 一行要約
    2. 内容の要点（箇条書き or 2〜3行）
    3. 自分へのメモ / キーワード（箇条書き）

### F-4. メール生成・送信

* 対象アイテムを1通のメールにまとめて送信する。

* メール件名フォーマット：

  * `【要約まとめ】YYYY-MM-DD 直近3日版`

    * `YYYY-MM-DD` は **バッチ実行日の JST** 日付。

* メール本文の構成例：

  ```text
  こんにちは。過去3日分のブックマークしたリンクの要約です。

  ====================
  1. タイトル: {Raindropアイテムのtitle}
  URL: {link}
  追加日時: {Raindropのcreated（JSTに変換して表示）}

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

    * 保存内容は、メールに掲載した要約からヘッダを除いた本文部（またはその短縮版）を想定。
  * 対象アイテムにタグ `配信済み` を追加する。
* 要約失敗時：

  * `note` は空のまま or 簡易的なエラーメッセージ（実装側で判断）。
  * タグ `配信済み` および `要約失敗` を追加する。

---

## 5. 非機能要件

* **バッチ実行頻度**: 3日に1回
* **実行時間帯**: JST 06:00

  * GitHub Actions の cron は UTC のため、`21:00 (前日)` に相当。
* **1件あたり要約長**: 最大500文字程度
* **メール1通あたり件数上限**: なし（新着対象はすべて掲載）
* **応答時間**: バッチ完了まで数分以内（実用上問題ない範囲なら許容）
* **可用性**: 個人ユースのため、たまの失敗は許容。
  失敗時は翌バッチまでに手動再実行可能な構成とする。

---

## 6. Raindrop 運用仕様

### 6.1 タグ運用

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

## 7. バッチ処理詳細設計

### 7.1 実行タイミング

* GitHub Actions の `schedule` トリガーを使用。
* JST 06:00 に相当するUTC時刻は前日21:00。
* cron 例：`0 21 */3 * *`

### 7.2 処理アルゴリズム（擬似コード）

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

    send_email_via_sendgrid(subject, email_body)

    for r in results:
        if r.status == "success":
            update_raindrop_note(r.item.id, r.summary)
            add_raindrop_tags(r.item.id, ["配信済み"])
        else:
            add_raindrop_tags(r.item.id, ["配信済み", "要約失敗"])
```

---

## 8. 外部API仕様（利用範囲）

※ 正確なエンドポイントパスやパラメータは実装時に公式ドキュメントを参照する。ここでは「どの種類の操作を行うか」を規定する。

### 8.1 Raindrop API

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

### 8.2 OpenAI API（Chat Completions）

* エンドポイント: `POST /v1/chat/completions`
* 使用モデル: `gpt-4.1-mini`（想定）
* 入力：

  * `messages`:

    * `system`: 日本語の要約ボットとしての振る舞い指示、出力形式、500文字制限を明示。
    * `user`: 抽出した本文テキスト（長すぎる場合は先頭数千文字にトリム）。
* 出力：

  * `choices[0].message.content` を要約テキストとして使用。

### 8.3 SendGrid API

* エンドポイント: `POST /v3/mail/send`
* 入力：

  * `from`: 送信元メールアドレス（設定値）
  * `to`: 宛先メールアドレス（設定値）
  * `subject`: 上記仕様の件名
  * `content`: `type: text/plain`（MVPではプレーンテキスト。将来的にHTML化も可）

---

## 9. 環境構成・設定

### 9.1 リポジトリ構成（例）

```text
.
├── .github
│   └── workflows
│       └── summarize-raindrop.yml   # GitHub Actions ワークフロー定義
├── src
│   ├── main.py                      # エントリポイント
│   ├── raindrop_client.py           # Raindrop API ラッパ
│   ├── text_extractor.py            # HTML取得 + 本文抽出
│   ├── summarizer.py                # OpenAI 要約ロジック
│   ├── mailer.py                    # SendGrid メール送信ロジック
│   └── utils.py                     # 共通ユーティリティ（時刻変換など）
└── requirements.txt
```

### 9.2 GitHub Actions Secrets

* `RAINDROP_TOKEN`
  Raindrop API トークン
* `OPENAI_API_KEY`
* `SENDGRID_API_KEY`
* `TO_EMAIL`
  宛先メールアドレス
* `FROM_EMAIL`
  送信元メールアドレス
* （任意）`OPENAI_MODEL`
  使用モデル名（デフォルト `gpt-4.1-mini`）

---

## 10. エラー処理・リトライ方針

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

* SendGridへの送信が失敗した場合：

  * **Raindrop側のタグ更新は行わない**（配信済み扱いにしない）。
  * GitHub Actions のログにエラーメッセージを出力。
  * 必要に応じて手動再実行できるようにしておく。
  * GHA は失敗扱いとし、処理を中断。
* Raindrop / OpenAI / SendGrid への接続エラーが発生した場合：

  * GHA は失敗扱いとし、処理を中断。

### 10.3 レート制限等

* OpenAI / Raindrop / SendGrid のレート制限に達した場合：

  * 処理を中断し、ログに詳細を出力。
  * 再実行は手動トリガーで行う想定。

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
