"""LINE Webhook 関連の Pydantic スキーマ。"""

from pydantic import BaseModel


class LineWebhookResponse(BaseModel):
    """LINE Webhook エンドポイントのレスポンス。"""

    status: str


class LineWebhookProcessResult(BaseModel):
    """LINE Webhook 処理結果（HTTP ステータス含む）。"""

    status: str = "ok"
    http_status_code: int = 200
    detail: str | None = None
