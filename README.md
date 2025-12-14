# Raindrop要約メール配信サービス（セットアップ手順）

Raindrop.io に保存したリンクを、GitHub Actions の定期実行で要約し、SendGrid 経由でメール配信します。

詳細仕様（エンジニア向け）は `docs/spec.md` を参照してください。

---

## 0. 用意するもの（アカウント）

- GitHub（このリポジトリをフォークして利用するのがおすすめ）
- Raindrop.io（ブックマーク保存先）
- OpenAI（要約用API）
- Brevo（メール送信用・推奨）
- （任意）SendGrid（メール送信用・フォールバックとして利用可能）

---

## 1. リポジトリを準備

1) GitHub 上でこのリポジトリをフォーク（または自分のリポジトリにコピー）

2) ローカルにクローン（GitHub の画面上だけで設定する場合、クローンは必須ではありません）

```bash
git clone <あなたのリポジトリURL>
```

---

## 2. OpenAI APIキーを取得

1) OpenAI の API Keys ページでキーを作成  
https://platform.openai.com/api-keys

> **Permissionsの設定方法**
Restricted タブで
Model capabilities → Responses：許可
他は すべて None（未選択）

2) 作成したキーを控える（あとで GitHub Secrets に登録）

---

## 3. Raindrop APIトークンを取得

1) Raindrop の Integrations / API token 画面でトークン(Test Token)を発行  
https://app.raindrop.io/settings/integrations

2) トークンを控える（あとで GitHub Secrets に登録）

---

## 4. Brevo を設定（メール送信・推奨）

### 4.1 Brevo の送信者（Sender）を用意

Brevo で送信元を登録します（画面の案内に従って Sender を作成してください）。

参考: https://developers.brevo.com/docs/getting-started

### 4.2 Brevo APIキーを作成

1) Brevo の `SMTP & API` から API key を作成  
2) 作成したキーを控える（あとで GitHub Secrets に登録）

---

## 5. SendGrid を設定（メール送信・任意）

### 5.1 Sender（送信元）を用意

SendGrid は送信元の設定が必須です。まずは簡単な方法として「Single Sender Verification」を使えます。

- SendGrid Single Sender Verification: https://docs.sendgrid.com/ui/sending-email/sender-verification

送信元メールアドレス（`FROM_EMAIL`）はここで認証したものを使ってください。

### 5.2 SendGrid APIキーを作成

1) SendGrid の API Keys で API key を作成  
https://docs.sendgrid.com/ui/account-and-settings/api-keys

2) 作成したキーを控える（あとで GitHub Secrets に登録）

### 5.3 迷惑メール対策（重要）

メールが「迷惑メール」に入る場合があります。以下を推奨します。

- SendGrid 側で Sender 認証（可能なら Domain Authentication も）を行う  
  https://docs.sendgrid.com/ui/account-and-settings/how-to-set-up-domain-authentication
- 受信側（Gmail など）で `FROM_EMAIL` を「連絡先に追加」/ フィルタで受信トレイへ振り分け
- 会社/学校メールの場合、ドメイン指定受信（ホワイトリスト）に `FROM_EMAIL` を追加

---

## 6. GitHub Actions に設定を登録

GitHub のリポジトリ画面で `Settings` → `Secrets and variables` → `Actions` を開きます。

### 5.1 Secrets（機密情報）

`Secrets` タブで以下を追加します。

- `RAINDROP_TOKEN`（Raindrop API token）
- `OPENAI_API_KEY`
- `BREVO_API_KEY`（Brevo API key。通常はこちらを設定）
- （任意）`SENDGRID_API_KEY`（SendGrid API key。フォールバックとして利用）
- （任意）`SUMMARY_SYSTEM_PROMPT`（要約プロンプトをカスタムしたい場合）

`SUMMARY_SYSTEM_PROMPT` は複数行でもOKです。未設定の場合はコード内のデフォルトプロンプトが使われます。

### 5.2 Variables（機密でない設定）

`Variables` タブで以下を追加します。

- `TO_EMAIL`（配信先メールアドレス）
- `FROM_EMAIL`（送信元メールアドレス）
- `FROM_NAME`（送信元表示名。例: `Raindrop要約メール配信サービス`）
- （任意）`OPENAI_MODEL`（例: `gpt-4.1-mini`）

---

## 6. GitHub Actions を実行する

1) リポジトリの `Actions` タブを開く  
2) `Summarize Raindrop` ワークフローを選ぶ  
3) `Run workflow` で手動実行（最初の動作確認におすすめ）

スケジュール実行（cron）は `.github/workflows/summarize-raindrop.yml` に定義されています。

---

## 7. 使い方（運用）

- Raindrop にリンクを保存します（保存先は「未整理」想定）。
- 一定日数分の新着を対象に要約してメールします。
- 次回以降の重複処理を避けるため、処理済みのアイテムにはタグ `配信済み` が付きます。
- `確認済み` タグが付いているアイテムは要約対象外です。

※ 要約のために、記事本文（および条件により画像URL）を OpenAI API に送信します。機密情報を含むページは保存しないでください。

---

## 8. よくあるトラブル

- メールが来ない
  - `Actions` の実行ログを確認（失敗している場合はログに出ます）
  - 迷惑メールフォルダを確認（上記「迷惑メール対策」を参照）
- Brevo/SendGrid のどちらが使われているか確認したい
  - GitHub Actions のログに `Using mail provider=brevo|sendgrid` と出ます
- OpenAI のエラーが多い
  - 一時的な 502/503/504 は 1 回だけリトライします
  - それ以外の失敗は該当リンクのみ失敗扱いになり、メールには「手動確認」として載ります
