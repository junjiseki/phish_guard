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
├── terraform
│   ├── main.tf                      # Cloud Run / Artifact Registry
│   ├── outputs.tf                   # デプロイ後のURL出力
│   ├── variables.tf                 # Terraform変数
│   ├── versions.tf                  # Terraform provider設定
│   └── terraform.tfvars.example     # 変数サンプル
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
| `DAILY_USER_REQUEST_LIMIT` | 任意 | 1ユーザーが1日に解析できる画像数 |
| `USER_REQUEST_LIMIT_STORE` | 任意 | 利用回数の保存先。ローカルは `memory`、Cloud Runは `firestore` を推奨。`firestore` は Cloud Run 上でのみ動作します |
| `GCP_PROJECT_ID` | Firestore利用時 | Firestore REST APIで使うGoogle Cloud project ID |
| `FIRESTORE_DATABASE_ID` | Firestore利用時 | Firestore database ID。既定値は `(default)` |
| `FIRESTORE_USAGE_COLLECTION` | Firestore利用時 | 利用回数を保存するFirestore collection |

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
https://xxxxx.trycloudflare.com/line/webhook
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

まず疎通だけ確認したい場合は、`.env` で署名検証を一時的に無効化できます。`/line/webhook` は空の `events` に対して `200 OK` を返します。

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
https://xxxxx.trycloudflare.com/line/webhook
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
curl -i -X POST http://localhost:8000/line/webhook \
  -H "Content-Type: application/json" \
  -d '{"destination":"local-check","events":[]}'
```

Cloudflare Tunnel経由でも確認します。

```bash
curl -i -X POST https://xxxxx.trycloudflare.com/line/webhook \
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

`/line/webhook` はPOST専用なので、ブラウザで開くと `405 Method Not Allowed` になる場合があります。これは正常です。

7. LINE DevelopersでWebhook verificationを確認します。

LINE Developers Consoleで対象のMessaging API Channelを開き、Messaging API settingsのWebhook URLに `https://xxxxx.trycloudflare.com/line/webhook` を設定します。その後、`Verify` を押します。

FastAPIのターミナルにLINEから送られたrequest bodyが表示され、LINE Developers側で成功表示になれば疎通確認は完了です。

8. LINE公式アカウントにSMSやメールのスクリーンショット画像を送ります。

9. 危険度、理由、対応方法がLINEに返信されれば成功です。

Verifyやcurl確認が終わったら、署名検証を有効に戻します。

```env
LINE_SIGNATURE_VERIFICATION_ENABLED=true
```

### FastAPIのWebhookエンドポイント

本番・ローカル共通の Webhook は [app/api/v1/endpoints/line.py](app/api/v1/endpoints/line.py) の `POST /line/webhook` です。署名検証とイベント処理は service 層に集約しています。

## Cloudflare Tunnel Troubleshooting

### LINE Verify が失敗する

- Webhook URLが `https://xxxxx.trycloudflare.com/line/webhook` になっているか確認します。
- `http://` ではなく `https://` を使います。
- FastAPIが `localhost:8000` で起動しているか確認します。
- `curl -i -X POST https://xxxxx.trycloudflare.com/line/webhook ...` が `200 OK` を返すか確認します。
- `curl: (6) Could not resolve host: xxxxx.trycloudflare.com` が出る場合は、そのQuick Tunnel URLが無効になっている可能性が高いです。`cloudflared tunnel --url http://localhost:8000` を起動し直し、新しく表示されたURLを使ってください。
- `/line/webhook` はPOST専用です。ブラウザで開いた結果だけで判断しないでください。

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

## Cloud RunをTerraformで構築する

開発環境をCloud RunへデプロイするTerraformコードは [terraform](terraform) にあります。

作成する主なリソース:

- Artifact Registry Docker repository
- Cloud Run service
- Cloud Run runtime service account
- Secret Manager secrets
- Cloud Run public invoker IAM
- 必要なGoogle Cloud APIの有効化

LINE Webhookから呼び出すため、既定ではCloud Runを未認証公開します。

### 前提コマンド

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

Terraformの変数ファイルを作成します。

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

`terraform/terraform.tfvars` の `project_id` と `image` を自分のGoogle Cloud projectに合わせます。

機密値をTerraform変数に入れると、Terraform stateにも保存されます。開発用途では簡単ですが、本番ではSecret Managerの値をTerraform外で管理し、`line_channel_secret_secret_id`、`line_channel_access_token_secret_id`、`gemini_api_key_secret_id` に既存secret IDを設定することを推奨します。

Cloud Runでは、利用回数制限の保存先としてFirestoreを使う設定が既定です。事前にFirestore Native modeのデータベースを作成し、`user_request_limit_store = "firestore"` のままデプロイしてください。ローカルや一時検証だけなら `memory` も使えますが、Cloud Runのインスタンス再起動や複数インスタンスでは正確な制限になりません。

### Artifact Registryを先に作成する

初回はDocker imageのpush先が必要なので、Artifact Registryだけ先に作成します。

```bash
cd terraform
terraform init
terraform apply \
  -target=google_project_service.required \
  -target=google_artifact_registry_repository.docker
```

### Docker imageをbuildしてpushする

```bash
cd ..
gcloud auth configure-docker asia-northeast1-docker.pkg.dev
docker build -t asia-northeast1-docker.pkg.dev/YOUR_PROJECT_ID/phish-guard/phish-guard-api:latest .
docker push asia-northeast1-docker.pkg.dev/YOUR_PROJECT_ID/phish-guard/phish-guard-api:latest
```

`terraform/terraform.tfvars` の `image` に同じimage URIを設定します。

### Cloud Runを作成する

```bash
cd terraform
terraform apply
```

完了後、次のoutputが表示されます。

```text
cloud_run_service_url
line_webhook_url
```

LINE DevelopersのWebhook URLには、本実装を使う場合は次を設定します。

```text
https://xxxxx.a.run.app/line/webhook
```

### 動作確認

```bash
curl -i https://xxxxx.a.run.app/health
```

LINE Webhook（署名検証を一時的に無効化している場合）:

```bash
curl -i -X POST https://xxxxx.a.run.app/line/webhook \
  -H "Content-Type: application/json" \
  -d '{"destination":"cloud-run-check","events":[]}'
```

署名検証が有効な場合、`/line/webhook` はLINE署名なしの curl を `400` で拒否します。疎通確認だけ行う場合は `.env` で `LINE_SIGNATURE_VERIFICATION_ENABLED=false` にしてください。

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

## GitHub Actions CI/CD

### CI（`.github/workflows/ci.yml`）

`main` / `develop` への push と pull request で次を実行します。

- `uv run ruff check .`
- `uv run pytest -q`
- `docker build`
- `terraform fmt -check` / `terraform validate`

### CD（`.github/workflows/cd.yml`）

`main` への push と手動実行で、Artifact Registry へ Docker image を push し、既存の Cloud Run サービスを更新します。

初回のインフラ作成は引き続き [Cloud RunをTerraformで構築する](#cloud-runをterraformで構築する) で行ってください。CD は image の更新のみを担当します。

#### 必要な GitHub 設定

Repository variables:

| 名前 | 例 | 必須 |
|------|-----|------|
| `GCP_PROJECT_ID` | `your-gcp-project-id` | はい |
| `GCP_REGION` | `asia-northeast1` | いいえ（未設定時は `asia-northeast1`） |

Repository secrets（Workload Identity Federation）:

| 名前 | 内容 |
|------|------|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/.../locations/global/workloadIdentityPools/.../providers/...` |
| `GCP_SERVICE_ACCOUNT` | `github-actions@your-project.iam.gserviceaccount.com` |

デプロイ用サービスアカウントには最低限次の権限が必要です。

- `roles/artifactregistry.writer`
- `roles/run.admin`
- `roles/iam.serviceAccountUser`（Cloud Run の実行 SA を指定する場合）

Workload Identity Federation の作成例:

以下の `YOUR_PROJECT_ID`、`PROJECT_NUMBER`、`GITHUB_OWNER`、`GITHUB_REPO` は自分の環境の値に置き換えてください。`--member` の `attribute.repository` は GitHub の `owner/repo` と一致している必要があります。

```bash
gcloud iam workload-identity-pools create github-actions \
  --project=YOUR_PROJECT_ID \
  --location=global \
  --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc github \
  --project=YOUR_PROJECT_ID \
  --location=global \
  --workload-identity-pool=github-actions \
  --display-name="GitHub" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"

gcloud iam service-accounts add-iam-policy-binding github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --project=YOUR_PROJECT_ID \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-actions/attribute.repository/GITHUB_OWNER/GITHUB_REPO"
```

例: リポジトリが `https://github.com/acme-corp/phish-guard` の場合、`GITHUB_OWNER/GITHUB_REPO` は `acme-corp/phish-guard` です。

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
