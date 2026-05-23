# Scam SMS and Phishing Mail Consultation AI

LINEで受け取ったSMSやメールのスクリーンショット画像をAIで確認し、フィッシングや詐欺の危険度を返信するMVPです。

高齢者にも分かりやすい短い文章で、危険度、理由、対応方法をLINEに返します。

## サービス概要

このサービスは、LINE公式アカウントに送られた画像を受け取り、画像内のSMSやメール文面をAIで読み取ります。

判定結果は次の3段階です。

- `low`: 危険な特徴は少なめ。ただし完全に安全とは言いません。
- `medium`: 注意が必要。判断できない場合もこの扱いにします。
- `high`: 危険な可能性が高い。URLや添付を開かないよう強く案内します。

返信には、理由と対応方法を最大3つずつ含めます。

## 技術構成

- Python 3.13
- FastAPI
- Pydantic / pydantic-settings
- Gemini API
- LINE Messaging API
- uv
- pytest
- Ruff
- Docker / Docker Compose

補足: もともとOpenAI Vision APIを使う想定の項目がありますが、現在の実装はGemini APIを使っています。そのためAPIキーは `GEMINI_API_KEY` を設定します。

## ディレクトリ構成

```text
.
├── app
│   ├── api
│   │   └── routes
│   │       └── line.py              # LINE Webhookの入口
│   ├── core
│   │   ├── config.py                # 環境変数の読み込み
│   │   └── logging.py               # ログ設定
│   ├── services
│   │   ├── analysis_service.py      # Gemini APIで画像解析
│   │   ├── line_service.py          # LINE署名検証、画像取得、返信
│   │   └── message_builder.py       # LINE返信文の作成
│   └── main.py                      # FastAPIアプリ本体
├── tests
│   ├── test_analysis_service.py
│   ├── test_line_service.py
│   └── test_message_builder.py
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

## 環境変数一覧

`.env.example` をコピーして `.env` を作成します。

```bash
cp .env.example .env
```

| 変数名 | 必須 | 説明 |
| --- | --- | --- |
| `APP_ENV` | 任意 | 実行環境。例: `local` |
| `APP_DEBUG` | 任意 | デバッグモード。ローカルでは `true` |
| `APP_LOG_LEVEL` | 任意 | ログレベル。例: `INFO` |
| `LINE_CHANNEL_SECRET` | 必須 | LINE DevelopersのChannel secret |
| `LINE_CHANNEL_ACCESS_TOKEN` | 必須 | LINE DevelopersのChannel access token |
| `GEMINI_API_KEY` | 必須 | Gemini APIキー |
| `GEMINI_MODEL` | 任意 | 使用するGeminiモデル。既定値は `gemini-2.5-flash` |
| `REQUEST_TIMEOUT_SECONDS` | 任意 | 外部APIへのタイムアウト秒数 |
| `MAX_IMAGE_BYTES` | 任意 | 受け付ける最大画像サイズ |

## LINE Developers設定手順

1. [LINE Developers](https://developers.line.biz/) にログインします。
2. Providerを作成します。
3. Messaging API Channelを作成します。
4. Channel basic settingsで `Channel secret` を確認し、`.env` の `LINE_CHANNEL_SECRET` に設定します。
5. Messaging API settingsで `Channel access token` を発行し、`.env` の `LINE_CHANNEL_ACCESS_TOKEN` に設定します。
6. Webhook URLを設定します。ローカル検証ではngrokのURLを使います。
7. `Use webhook` を有効にします。
8. LINE公式アカウントを友だち追加し、画像を送れる状態にします。

Webhook URLの例:

```text
https://example.ngrok-free.app/line/webhook
```

## OpenAI APIキー設定

現在の実装ではOpenAI APIキーは使いません。

AI解析にはGemini APIを使うため、`.env` に `GEMINI_API_KEY` を設定してください。

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
```

Gemini APIキーはGoogle AI Studioなどで発行します。

## ローカル起動方法

依存関係をインストールします。

```bash
uv sync
```

FastAPIを起動します。

```bash
uv run uvicorn app.main:app --reload
```

起動確認:

```bash
curl http://localhost:8000/health
```

次のように返れば起動できています。

```json
{"status":"ok"}
```

Dockerで起動する場合:

```bash
docker compose up --build
```

## ngrokでのWebhook検証方法

LINE DevelopersからローカルPCへWebhookを送るには、ngrokなどでローカルサーバーを外部公開します。

1. FastAPIを起動します。

```bash
uv run uvicorn app.main:app --reload
```

2. 別のターミナルでngrokを起動します。

```bash
ngrok http 8000
```

3. 表示されたHTTPS URLをコピーします。

例:

```text
https://example.ngrok-free.app
```

4. LINE DevelopersのWebhook URLに次を設定します。

```text
https://example.ngrok-free.app/line/webhook
```

5. `Verify` を押して接続確認します。

6. LINE公式アカウントにSMSやメールのスクリーンショット画像を送ります。

7. 危険度、理由、対応方法がLINEに返信されれば成功です。

## テスト実行方法

Ruff:

```bash
uv run ruff check .
```

pytest:

```bash
uv run pytest
```

現在のテスト対象:

- 危険度別のLINE返信文生成
- Gemini APIレスポンスJSONのパース
- LINE署名検証
- 画像以外のメッセージ時の案内文

テストでは外部APIを実際には呼びません。

## セキュリティ方針

このMVPでは、個人情報や画像の扱いをできるだけ小さくしています。

- 画像を保存しません。
- SMSやメール本文を保存しません。
- 画像本文やAI解析本文をログに出しません。
- LINE署名を検証し、不正なWebhookを拒否します。
- AIの判定は参考情報です。
- `low` の場合でも「完全に安全」とは断定しません。
- 不安な場合は、公式アプリ、公式サイト、公式窓口、家族への相談を案内します。

注意: AIの判定は誤ることがあります。最終判断は、公式窓口や信頼できる人への確認と合わせて行ってください。

## 今後の拡張案

- 家族通知
  - 高リスク判定時に、あらかじめ登録した家族へ通知する。

- 判定履歴
  - 過去の相談内容や判定結果を確認できるようにする。
  - 保存する場合は、個人情報の扱いと保存期間を明確にする。

- 課金
  - 無料枠と有料枠を分ける。
  - 月額課金や回数制限を導入する。

- 管理画面
  - 利用状況、エラー件数、問い合わせ状況を確認できる画面を作る。
  - 高リスク件数の集計や運用メモを管理する。

## 主な処理の流れ

```text
LINEで画像を送信
  ↓
POST /line/webhook
  ↓
LINE署名を検証
  ↓
LINE Message Content APIで画像を取得
  ↓
Gemini APIで画像内のSMS/メール文面を解析
  ↓
危険度、理由、対応方法を作成
  ↓
高齢者にも分かりやすい文章に整形
  ↓
LINE Reply APIで返信
```
