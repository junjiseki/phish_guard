import asyncio
import base64
import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings
from app.services.analysis_service import PhishingAnalysis, analyze_phishing_image
from app.services.message_builder import build_line_reply

logger = logging.getLogger(__name__)

LINE_SIGNATURE_HEADER = "x-line-signature"
LINE_CONTENT_API_BASE_URL = "https://api-data.line.me/v2/bot/message"
LINE_REPLY_API_URL = "https://api.line.me/v2/bot/message/reply"

ERROR_REPLY_MESSAGE = "\n".join(
    [
        "画像をうまく確認できませんでした。",
        "",
        "少し時間をおいて、もう一度送ってください。",
        "不安な場合は、URLや添付を開かず、家族や公式窓口に相談してください。",
    ],
)

NON_IMAGE_REPLY_MESSAGE = "\n".join(
    [
        "調べたいSMSやメールの画面を、画像で送ってください。",
        "",
        "URLや添付がある場合は、開く前に確認しましょう。",
        "不安な場合は家族や公式窓口に相談してください。",
    ],
)

AnalysisFunction = Callable[[bytes, str | None], Awaitable[PhishingAnalysis]]


class LineWebhookService:
    def __init__(
        self,
        settings: Settings | None = None,
        analysis_function: AnalysisFunction = analyze_phishing_image,
    ) -> None:
        self.settings = settings or get_settings()
        self.analysis_function = analysis_function

    async def handle_webhook(self, body: bytes, signature: str | None) -> None:
        if not verify_line_signature(
            body=body,
            signature=signature,
            channel_secret=self.settings.line_channel_secret,
        ):
            raise LineSignatureError

        for event in parse_line_events(body):
            await self._handle_event(event)

    async def _handle_event(self, event: dict[str, Any]) -> None:
        reply_token = event.get("replyToken")
        if not isinstance(reply_token, str) or not reply_token:
            return

        try:
            reply_text = await self._build_reply_text(event)
        except Exception as exc:
            logger.warning("LINE event handling failed: %s", type(exc).__name__)
            reply_text = ERROR_REPLY_MESSAGE

        try:
            await self.reply_text(reply_token=reply_token, text=reply_text)
        except LineServiceError as exc:
            logger.warning("LINE reply failed: %s", type(exc).__name__)

    async def _build_reply_text(self, event: dict[str, Any]) -> str:
        message = event.get("message")
        if not isinstance(message, dict) or message.get("type") != "image":
            return NON_IMAGE_REPLY_MESSAGE

        message_id = message.get("id")
        if not isinstance(message_id, str) or not message_id:
            raise LineWebhookError

        content = await self.get_message_content(message_id=message_id)
        validate_image_content(content, self.settings.max_image_bytes)

        analysis = await self.analysis_function(
            image_bytes=content.body,
            mime_type=content.mime_type,
        )
        return build_line_reply(analysis)

    async def get_message_content(self, message_id: str) -> "LineMessageContent":
        return await asyncio.to_thread(self._get_message_content, message_id)

    def _get_message_content(self, message_id: str) -> "LineMessageContent":
        if not self.settings.line_channel_access_token:
            raise LineConfigurationError

        quoted_message_id = urllib.parse.quote(message_id, safe="")
        url = f"{LINE_CONTENT_API_BASE_URL}/{quoted_message_id}/content"
        request = urllib.request.Request(
            url=url,
            headers={
                "Authorization": f"Bearer {self.settings.line_channel_access_token}",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.settings.request_timeout_seconds,
            ) as response:
                body = response.read(self.settings.max_image_bytes + 1)
                mime_type = response.headers.get_content_type()
                return LineMessageContent(body=body, mime_type=mime_type)
        except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            raise LineContentFetchError from exc

    async def reply_text(self, reply_token: str, text: str) -> None:
        await asyncio.to_thread(self._reply_text, reply_token, text)

    def _reply_text(self, reply_token: str, text: str) -> None:
        if not self.settings.line_channel_access_token:
            raise LineConfigurationError

        request_body = {
            "replyToken": reply_token,
            "messages": [
                {
                    "type": "text",
                    "text": text,
                },
            ],
        }
        request = urllib.request.Request(
            url=LINE_REPLY_API_URL,
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.line_channel_access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.settings.request_timeout_seconds,
            ):
                return
        except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            raise LineReplyError from exc


@dataclass(frozen=True)
class LineMessageContent:
    body: bytes
    mime_type: str


class LineServiceError(Exception):
    pass


class LineSignatureError(LineServiceError):
    pass


class LineWebhookError(LineServiceError):
    pass


class LineContentFetchError(LineServiceError):
    pass


class LineImageTooLargeError(LineServiceError):
    pass


class LineReplyError(LineServiceError):
    pass


class LineConfigurationError(LineServiceError):
    pass


def parse_line_events(body: bytes) -> list[dict[str, Any]]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LineWebhookError from exc

    if not isinstance(payload, dict):
        raise LineWebhookError

    events = payload.get("events", [])
    if not isinstance(events, list):
        raise LineWebhookError

    return [event for event in events if isinstance(event, dict)]


def validate_image_content(content: LineMessageContent, max_image_bytes: int) -> None:
    if not content.body:
        raise LineContentFetchError

    if len(content.body) > max_image_bytes:
        raise LineImageTooLargeError

    if not content.mime_type.startswith("image/"):
        raise LineContentFetchError


def verify_line_signature(
    body: bytes,
    signature: str | None,
    channel_secret: str,
) -> bool:
    if not signature or not channel_secret:
        return False

    digest = hmac.new(
        channel_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    expected_signature = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected_signature, signature)
