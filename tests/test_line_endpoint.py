from fastapi.testclient import TestClient

from app.api.deps import get_line_webhook_service
from app.core.config import Settings
from app.main import app
from app.services.line_service import LineWebhookService

HTTP_STATUS_OK = 200
HTTP_STATUS_BAD_REQUEST = 400


def test_line_webhook_returns_ok_for_empty_events() -> None:
    app.dependency_overrides[get_line_webhook_service] = lambda: LineWebhookService(
        Settings(
            LINE_CHANNEL_SECRET="",
            LINE_SIGNATURE_VERIFICATION_ENABLED=False,
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/line/webhook",
        json={"events": []},
    )

    app.dependency_overrides.clear()

    assert response.status_code == HTTP_STATUS_OK
    assert response.json() == {"status": "ok"}


def test_line_webhook_returns_400_for_invalid_signature() -> None:
    app.dependency_overrides[get_line_webhook_service] = lambda: LineWebhookService(
        Settings(
            LINE_CHANNEL_SECRET="secret",
            LINE_SIGNATURE_VERIFICATION_ENABLED=True,
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/line/webhook",
        json={"events": []},
    )

    app.dependency_overrides.clear()

    assert response.status_code == HTTP_STATUS_BAD_REQUEST
    assert response.json() == {"detail": "Invalid LINE signature"}
