"""LINE Webhook 関連の Pydantic スキーマ。"""

from pydantic import BaseModel


class LineWebhookResponse(BaseModel):
    """LINE Webhook エンドポイントのレスポンス。"""

    status: str
