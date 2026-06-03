"""FastAPI 依存関係。"""

from app.services.line_service import LineWebhookService


def get_line_webhook_service() -> LineWebhookService:
    """LINE Webhook 用サービスを返す。"""
    return LineWebhookService()
