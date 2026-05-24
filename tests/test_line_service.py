import asyncio
import base64
import hashlib
import hmac

import pytest

from app.core.config import Settings
from app.schemas.analysis import PhishingAnalysis
from app.services.line_service import (
    NON_IMAGE_REPLY_MESSAGE,
    LineContentFetchError,
    LineMessageContent,
    LineWebhookService,
    parse_line_events,
    validate_image_content,
    verify_line_signature,
)


def build_signature(body: bytes, channel_secret: str) -> str:
    digest = hmac.new(
        channel_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def test_verify_line_signature_accepts_valid_signature() -> None:
    body = b'{"events":[]}'
    signature = build_signature(body, "secret")

    assert verify_line_signature(body, signature, "secret")


def test_verify_line_signature_rejects_invalid_signature() -> None:
    body = b'{"events":[]}'

    assert not verify_line_signature(body, "bad-signature", "secret")
    assert not verify_line_signature(body, None, "secret")
    assert not verify_line_signature(body, "bad-signature", "")


def test_non_image_message_returns_guidance_text() -> None:
    service = LineWebhookService(Settings(LINE_CHANNEL_SECRET="secret"))
    event = {
        "replyToken": "reply-token",
        "message": {
            "type": "text",
            "id": "message-id",
            "text": "hello",
        },
    }

    reply = asyncio.run(service._build_reply_text(event))

    assert reply == NON_IMAGE_REPLY_MESSAGE
    assert "画像で送ってください" in reply
    assert "家族や公式窓口" in reply


def test_parse_line_events_ignores_non_dict_events() -> None:
    events = parse_line_events(b'{"events":[{"replyToken":"token"},"ignored"]}')

    assert events == [{"replyToken": "token"}]


def test_validate_image_content_rejects_non_image_content() -> None:
    content = LineMessageContent(body=b"text", mime_type="text/plain")

    with pytest.raises(LineContentFetchError):
        validate_image_content(content, max_image_bytes=1024)


def test_image_message_uses_injected_analysis_function() -> None:
    async def fake_analysis(
        image_bytes: bytes,
        mime_type: str | None,
    ) -> PhishingAnalysis:
        assert image_bytes == b"image"
        assert mime_type == "image/png"
        return PhishingAnalysis(
            risk_level="high",
            summary="危険な可能性があります",
            reasons=["偽の案内の可能性があります"],
            actions=["URLは開かないでください"],
        )

    async def fake_get_message_content(message_id: str) -> LineMessageContent:
        assert message_id == "message-id"
        return LineMessageContent(body=b"image", mime_type="image/png")

    service = LineWebhookService(
        Settings(LINE_CHANNEL_SECRET="secret"),
        analysis_function=fake_analysis,
    )
    service.get_message_content = fake_get_message_content  # type: ignore[method-assign]
    event = {
        "replyToken": "reply-token",
        "message": {
            "type": "image",
            "id": "message-id",
        },
    }

    reply = asyncio.run(service._build_reply_text(event))

    assert "危険な可能性があります" in reply
    assert "URLは開かないでください" in reply
