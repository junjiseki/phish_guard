import asyncio
import base64
import hashlib
import hmac

import pytest

from app.core.config import Settings
from app.schemas.analysis import PhishingAnalysis
from app.services.line_service import (
    DAILY_USER_REQUEST_LIMIT,
    NON_IMAGE_REPLY_MESSAGE,
    REQUEST_LIMIT_EXCEEDED_REPLY_MESSAGE,
    DailyUserRequestLimiter,
    LineContentFetchError,
    LineMessageContent,
    LineSignatureError,
    LineWebhookService,
    extract_line_user_id,
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


def test_handle_webhook_rejects_missing_signature_by_default() -> None:
    service = LineWebhookService(
        Settings(
            LINE_CHANNEL_SECRET="secret",
            LINE_SIGNATURE_VERIFICATION_ENABLED=True,
        ),
    )

    with pytest.raises(LineSignatureError):
        asyncio.run(service.handle_webhook(body=b'{"events":[]}', signature=None))


def test_handle_webhook_can_skip_signature_for_local_ngrok_check() -> None:
    service = LineWebhookService(
        Settings(
            LINE_CHANNEL_SECRET="",
            LINE_SIGNATURE_VERIFICATION_ENABLED=False,
        ),
    )

    asyncio.run(service.handle_webhook(body=b'{"events":[]}', signature=None))


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


def test_daily_user_request_limiter_allows_only_configured_count() -> None:
    limiter = DailyUserRequestLimiter(limit=DAILY_USER_REQUEST_LIMIT)

    assert limiter.allow("user-id")
    assert limiter.allow("user-id")
    assert not limiter.allow("user-id")
    assert limiter.allow("another-user-id")


def test_handle_event_returns_limit_message_after_daily_limit() -> None:
    replies: list[str] = []

    async def fake_reply_text(reply_token: str, text: str) -> None:
        assert reply_token
        replies.append(text)

    service = LineWebhookService(
        Settings(LINE_CHANNEL_SECRET="secret"),
        request_limiter=DailyUserRequestLimiter(limit=2),
    )
    service.reply_text = fake_reply_text  # type: ignore[method-assign]

    event = {
        "replyToken": "reply-token",
        "source": {
            "type": "user",
            "userId": "user-id",
        },
        "message": {
            "type": "text",
            "id": "message-id",
            "text": "hello",
        },
    }

    asyncio.run(service._handle_event(event))
    asyncio.run(service._handle_event(event))
    asyncio.run(service._handle_event(event))

    assert replies == [
        NON_IMAGE_REPLY_MESSAGE,
        NON_IMAGE_REPLY_MESSAGE,
        REQUEST_LIMIT_EXCEEDED_REPLY_MESSAGE,
    ]


def test_extract_line_user_id_returns_user_source_id() -> None:
    assert (
        extract_line_user_id(
            {
                "source": {
                    "type": "user",
                    "userId": "user-id",
                },
            },
        )
        == "user-id"
    )
    assert extract_line_user_id({"source": {"type": "group"}}) is None


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
