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

開発環境でCloudflare Tunnelを使ってLINE Webhookを確認する最小構成は次の通りです。

```text
app/
  main.py
README.md
Makefile
```

現在のMVP全体の構成は次の通りです。

```text
.
├── app
│   ├── api
│   │   └── v1
│   │       └── endpoints
│   │           └── line.py          # LINE Webhookの本実装
│   ├── core
│   │   ├── config.py                # 環境変数の読み込み
│   │   └── logging.py               # ログ設定
|   ├── schemas/                     # Pydantic スキーマ
│   |   ├── analysis.py
│   |   └── line.py
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
├── Makefile
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
| `LINE_SIGNATURE_VERIFICATION_ENABLED` | 任意 | LINE署名検証を有効にするか。既定値は `true`。curlやCloudflare Tunnelの疎通確認だけなら一時的に `false` にできます |
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
6. Webhook URLを設定します。ローカル検証ではCloudflare TunnelのURLを使います。
7. `Use webhook` を有効にします。
8. LINE公式アカウントを友だち追加し、画像を送れる状態にします。

Webhook URLの例:

```text
https://xxxxx.trycloudflare.com/callback
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
uv run python -m uvicorn app.main:app --reload
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

Makefileを使う場合:

```bash
make run
```

## Cloudflare TunnelでのWebhook検証方法

LINE DevelopersからローカルPCへWebhookを送るには、Cloudflare TunnelでローカルサーバーをHTTPS公開します。

Quick Tunnelは開発用途向けです。URLは起動するたびに変わります。本番運用では固定URLを使えるNamed Tunnelを推奨します。HTTPS/TLSはCloudflare側で自動対応されます。

### cloudflaredのインストール

macOSではHomebrewでインストールします。

```bash
brew install cloudflared
```

インストール確認:

```bash
cloudflared --version
```

### Quick Tunnelでlocalhost:8000を公開する

まず疎通だけ確認したい場合は、`.env` で署名検証を一時的に無効化できます。`/callback` の最小サンプルは署名検証を行わず、リクエストbodyをログ出力して `200 OK` を返します。

```env
LINE_SIGNATURE_VERIFICATION_ENABLED=false
```

注意: 本番運用や実際のLINE連携確認では `true` に戻し、`LINE_CHANNEL_SECRET` を必ず設定してください。

1. FastAPIを起動します。

```bash
uv run python -m uvicorn app.main:app --reload
```

Makefileを使う場合:

```bash
make run
```

2. 別のターミナルでCloudflare Quick Tunnelを起動します。

```bash
cloudflared tunnel --url http://localhost:8000
```

Makefileを使う場合:

```bash
make tunnel
```

3. 表示されたHTTPS URLをコピーします。

例:

```text
https://xxxxx.trycloudflare.com
```

4. LINE DevelopersのWebhook URLに次を設定します。

```text
https://xxxxx.trycloudflare.com/callback
```

5. ローカルから疎通確認します。

```bash
curl -i http://localhost:8000/health
```

次のように `200 OK` が返ればFastAPIは起動しています。

```text
HTTP/1.1 200 OK
```

Webhookエンドポイントをローカルで確認します。

```bash
curl -i -X POST http://localhost:8000/callback \
  -H "Content-Type: application/json" \
  -d '{"destination":"local-check","events":[]}'
```

Cloudflare Tunnel経由でも確認します。

```bash
curl -i -X POST https://xxxxx.trycloudflare.com/callback \
  -H "Content-Type: application/json" \
  -d '{"destination":"cloudflare-check","events":[]}'
```

どちらも次のように `200 OK` が返れば、LINE Developersから到達できる準備ができています。

```text
HTTP/1.1 200 OK
```

6. ブラウザで次のURLを開き、FastAPIがngrok経由で見えていることを確認します。

```text
https://xxxxx.trycloudflare.com/health
```

`/callback` はPOST専用なので、ブラウザで開くと `405 Method Not Allowed` になる場合があります。これは正常です。

7. LINE DevelopersでWebhook verificationを確認します。

LINE Developers Consoleで対象のMessaging API Channelを開き、Messaging API settingsのWebhook URLに `https://xxxxx.trycloudflare.com/callback` を設定します。その後、`Verify` を押します。

FastAPIのターミナルにLINEから送られたrequest bodyが表示され、LINE Developers側で成功表示になれば疎通確認は完了です。

8. LINE公式アカウントにSMSやメールのスクリーンショット画像を送ります。

9. 危険度、理由、対応方法がLINEに返信されれば成功です。

Verifyやcurl確認が終わったら、署名検証を有効に戻します。

```env
LINE_SIGNATURE_VERIFICATION_ENABLED=true
```

### FastAPIのWebhook最小サンプル

[app/main.py](app/main.py) にはCloudflare Tunnelの疎通確認用に次のエンドポイントがあります。

```python
from fastapi import FastAPI, Request

app = FastAPI()


@app.post("/callback")
async def callback(request: Request):
    body = await request.body()
    print(body.decode())
    return {"status": "ok"}
```

実際のアプリでは既存のFastAPIアプリに `/callback` を追加しています。

## Cloudflare Tunnel Troubleshooting

### LINE Verify が失敗する

- Webhook URLが `https://xxxxx.trycloudflare.com/callback` になっているか確認します。
- `http://` ではなく `https://` を使います。
- FastAPIが `localhost:8000` で起動しているか確認します。
- `curl -i -X POST https://xxxxx.trycloudflare.com/callback ...` が `200 OK` を返すか確認します。
- `curl: (6) Could not resolve host: xxxxx.trycloudflare.com` が出る場合は、そのQuick Tunnel URLが無効になっている可能性が高いです。`cloudflared tunnel --url http://localhost:8000` を起動し直し、新しく表示されたURLを使ってください。
- `/callback` はPOST専用です。ブラウザで開いた結果だけで判断しないでください。

### 502 エラー

- FastAPIが停止している可能性があります。`make run` または `uv run python -m uvicorn app.main:app --reload` で起動してください。
- Cloudflare Tunnelの転送先が `http://localhost:8000` になっているか確認します。
- ポート番号を変えた場合は、`cloudflared tunnel --url http://localhost:<port>` も合わせて変更します。

### localhost 接続失敗

- `curl -i http://localhost:8000/health` を実行して `200 OK` が返るか確認します。
- 既に別プロセスが8000番ポートを使っていないか確認します。
- Dockerで起動している場合は、コンテナが8000番ポートを公開しているか確認します。

### tunnel URL が毎回変わる

- Quick TunnelのURLは起動するたびに変わります。開発用として毎回LINE DevelopersのWebhook URLを更新してください。
- `cloudflared` を停止した、ターミナルを閉じた、PCがスリープした、ネットワークが切り替わった場合は、以前の `https://xxxxx.trycloudflare.com` が名前解決できなくなることがあります。
- `curl: (6) Could not resolve host` が出たら、古いURLを使っていないか確認し、Quick Tunnelを起動し直して新しいURLに差し替えます。
- 固定URLが必要な場合は、本番や継続開発用にNamed Tunnelを使います。

### cloudflared command not found

- Homebrewでインストールします。

```bash
brew install cloudflared
```

- インストール後にシェルを開き直すか、PATHが通っているか確認します。

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
