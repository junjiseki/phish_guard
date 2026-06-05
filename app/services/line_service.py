import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from app.core.config import Settings, get_settings
from app.schemas.analysis import PhishingAnalysis
from app.schemas.line import LineWebhookProcessResult
from app.services.analysis_service import analyze_phishing_image
from app.services.message_builder import build_line_reply

logger = logging.getLogger(__name__)

LINE_SIGNATURE_HEADER = "x-line-signature"
LINE_CONTENT_API_BASE_URL = "https://api-data.line.me/v2/bot/message"
LINE_REPLY_API_URL = "https://api.line.me/v2/bot/message/reply"
HTTP_STATUS_OK = 200
HTTP_STATUS_BAD_REQUEST = 400
INVALID_LINE_SIGNATURE_DETAIL = "Invalid LINE signature"
DAILY_USER_REQUEST_LIMIT = 2
DAILY_USER_REQUEST_LIMIT_TIMEZONE = "Asia/Tokyo"
USER_REQUEST_LIMIT_STORE_FIRESTORE = "firestore"
FIRESTORE_API_BASE_URL = "https://firestore.googleapis.com/v1"
GCP_METADATA_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/"
    "service-accounts/default/token"
)

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

REQUEST_LIMIT_EXCEEDED_REPLY_MESSAGE = "\n".join(
    [
        "本日の利用回数が上限に達しました。",
        "",
        f"1日に確認できる画像は{DAILY_USER_REQUEST_LIMIT}回までです。",
        "明日また利用してください。",
        "",
        "不安な場合は、URLや添付を開かず、家族や公式窓口に相談してください。",
    ],
)

AnalysisFunction = Callable[[bytes, str | None], Awaitable[PhishingAnalysis]]


class UserRequestLimiter(Protocol):
    def allow(self, user_id: str) -> bool: ...


@dataclass
class UserRequestUsage:
    used_on: str
    count: int


class DailyUserRequestLimiter:
    def __init__(
        self,
        limit: int = DAILY_USER_REQUEST_LIMIT,
        timezone_name: str = DAILY_USER_REQUEST_LIMIT_TIMEZONE,
    ) -> None:
        self.limit = limit
        self.timezone = ZoneInfo(timezone_name)
        self._usage_by_user_id: dict[str, UserRequestUsage] = {}
        self._lock = Lock()

    def allow(self, user_id: str) -> bool:
        today = datetime.now(self.timezone).date().isoformat()

        with self._lock:
            usage = self._usage_by_user_id.get(user_id)
            if usage is None or usage.used_on != today:
                self._usage_by_user_id[user_id] = UserRequestUsage(
                    used_on=today,
                    count=1,
                )
                return True

            if usage.count >= self.limit:
                return False

            usage.count += 1
            return True


daily_user_request_limiter = DailyUserRequestLimiter()
_memory_limiter_lock = Lock()
_memory_limiters_by_limit: dict[int, DailyUserRequestLimiter] = {
    DAILY_USER_REQUEST_LIMIT: daily_user_request_limiter,
}


class LineWebhookService:
    def __init__(
        self,
        settings: Settings | None = None,
        analysis_function: AnalysisFunction = analyze_phishing_image,
        request_limiter: UserRequestLimiter | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.analysis_function = analysis_function
        self.request_limiter = request_limiter or build_request_limiter(self.settings)

    async def process_webhook(
        self,
        body: bytes,
        signature: str | None,
    ) -> LineWebhookProcessResult:
        if self.settings.line_signature_verification_enabled:
            if not verify_line_signature(
                body=body,
                signature=signature,
                channel_secret=self.settings.line_channel_secret,
            ):
                return LineWebhookProcessResult(
                    http_status_code=HTTP_STATUS_BAD_REQUEST,
                    detail=INVALID_LINE_SIGNATURE_DETAIL,
                )
        else:
            logger.warning("LINE signature verification is disabled")

        try:
            events = parse_line_events(body)
        except LineWebhookError:
            logger.warning("LINE webhook payload is invalid")
            return LineWebhookProcessResult()

        await self._process_events(events)
        return LineWebhookProcessResult()

    async def _process_events(self, events: list[dict[str, Any]]) -> None:
        for event in events:
            try:
                await self._handle_event(event)
            except Exception as exc:
                logger.warning(
                    "LINE event processing failed: %s",
                    type(exc).__name__,
                    exc_info=True,
                )

    async def _handle_event(self, event: dict[str, Any]) -> None:
        reply_token = event.get("replyToken")
        if not isinstance(reply_token, str) or not reply_token:
            return

        try:
            reply_text = await self._build_reply_text(event)
        except Exception as exc:
            logger.warning(
                "LINE event handling failed: %s",
                type(exc).__name__,
                exc_info=True,
            )
            reply_text = ERROR_REPLY_MESSAGE

        try:
            await self.reply_text(reply_token=reply_token, text=reply_text)
        except LineServiceError as exc:
            logger.warning("LINE reply failed: %s", type(exc).__name__)

    async def _is_request_allowed(self, event: dict[str, Any]) -> bool:
        user_id = extract_line_user_id(event)
        if user_id is None:
            return True

        return await asyncio.to_thread(self.request_limiter.allow, user_id)

    async def _build_reply_text(self, event: dict[str, Any]) -> str:
        message = event.get("message")
        if not isinstance(message, dict) or message.get("type") != "image":
            return NON_IMAGE_REPLY_MESSAGE

        if not await self._is_request_allowed(event):
            return REQUEST_LIMIT_EXCEEDED_REPLY_MESSAGE

        message_id = message.get("id")
        if not isinstance(message_id, str) or not message_id:
            raise LineWebhookError

        content = await self.get_message_content(message_id=message_id)
        validate_image_content(content, self.settings.max_image_bytes)

        analysis = await self.analysis_function(content.body, content.mime_type)
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


def extract_line_user_id(event: dict[str, Any]) -> str | None:
    source = event.get("source")
    if not isinstance(source, dict):
        return None

    user_id = source.get("userId")
    if not isinstance(user_id, str) or not user_id:
        return None

    return user_id


class FirestoreDailyUserRequestLimiter:
    def __init__(
        self,
        *,
        project_id: str,
        database_id: str,
        collection: str,
        limit: int,
        timeout_seconds: int,
        timezone_name: str = DAILY_USER_REQUEST_LIMIT_TIMEZONE,
    ) -> None:
        if not project_id:
            raise LineConfigurationError

        self.project_id = project_id
        self.database_id = database_id
        self.collection = collection
        self.limit = limit
        self.timeout_seconds = timeout_seconds
        self.timezone = ZoneInfo(timezone_name)
        self._token_lock = Lock()
        self._access_token = ""
        self._access_token_expires_at = 0.0

    def allow(self, user_id: str) -> bool:
        today = datetime.now(self.timezone).date().isoformat()
        document_name = self._document_name(user_id=user_id, used_on=today)
        transaction = self._begin_transaction()

        try:
            document = self._lookup_document(
                document_name=document_name,
                transaction=transaction,
            )
            count = self._document_count(document)
            if count >= self.limit:
                self._rollback_transaction(transaction)
                return False

            self._commit_usage(
                document_name=document_name,
                user_id=user_id,
                used_on=today,
                count=count + 1,
                transaction=transaction,
            )
            return True
        except Exception:
            self._rollback_transaction(transaction)
            raise

    def _begin_transaction(self) -> str:
        response = self._post_json(
            path=":beginTransaction",
            body={"options": {"readWrite": {}}},
        )
        transaction = response.get("transaction")
        if not isinstance(transaction, str) or not transaction:
            raise LineConfigurationError
        return transaction

    def _lookup_document(
        self,
        *,
        document_name: str,
        transaction: str,
    ) -> dict[str, Any] | None:
        response = self._post_json(
            path=":batchGet",
            body={
                "documents": [document_name],
                "transaction": transaction,
            },
        )

        if isinstance(response, list):
            response = response[0] if response else {}

        found = response.get("found")
        if isinstance(found, dict):
            return found
        return None

    def _commit_usage(
        self,
        *,
        document_name: str,
        user_id: str,
        used_on: str,
        count: int,
        transaction: str,
    ) -> None:
        self._post_json(
            path=":commit",
            body={
                "transaction": transaction,
                "writes": [
                    {
                        "update": {
                            "name": document_name,
                            "fields": {
                                "user_id_hash": {
                                    "stringValue": hashlib.sha256(
                                        user_id.encode("utf-8"),
                                    ).hexdigest(),
                                },
                                "used_on": {"stringValue": used_on},
                                "count": {"integerValue": str(count)},
                            },
                        },
                    },
                ],
            },
        )

    def _rollback_transaction(self, transaction: str) -> None:
        try:
            self._post_json(path=":rollback", body={"transaction": transaction})
        except LineServiceError:
            logger.warning("Firestore transaction rollback failed")

    def _document_name(self, *, user_id: str, used_on: str) -> str:
        document_id = hashlib.sha256(f"{user_id}:{used_on}".encode()).hexdigest()
        return (
            f"projects/{self.project_id}/databases/{self.database_id}/documents/"
            f"{self.collection}/{document_id}"
        )

    def _document_count(self, document: dict[str, Any] | None) -> int:
        if document is None:
            return 0

        fields = document.get("fields")
        if not isinstance(fields, dict):
            return 0

        count_field = fields.get("count")
        if not isinstance(count_field, dict):
            return 0

        count = count_field.get("integerValue")
        if not isinstance(count, str):
            return 0

        try:
            return int(count)
        except ValueError:
            return 0

    def _post_json(self, *, path: str, body: dict[str, Any]) -> Any:
        quoted_project_id = urllib.parse.quote(self.project_id, safe="")
        quoted_database_id = urllib.parse.quote(self.database_id, safe="")
        database_path = (
            f"projects/{quoted_project_id}/databases/{quoted_database_id}/documents"
        )
        url = f"{FIRESTORE_API_BASE_URL}/{database_path}{path}"
        request = urllib.request.Request(
            url=url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._get_access_token()}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            raise LineConfigurationError from exc

    def _get_access_token(self) -> str:
        with self._token_lock:
            if self._access_token and time.monotonic() < self._access_token_expires_at:
                return self._access_token

            request = urllib.request.Request(
                url=GCP_METADATA_TOKEN_URL,
                headers={"Metadata-Flavor": "Google"},
                method="GET",
            )
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self.timeout_seconds,
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
                raise LineConfigurationError from exc

            access_token = payload.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise LineConfigurationError

            expires_in = payload.get("expires_in")
            if not isinstance(expires_in, int):
                expires_in = 300

            self._access_token = access_token
            self._access_token_expires_at = time.monotonic() + max(expires_in - 60, 1)
            return access_token


def build_request_limiter(settings: Settings) -> UserRequestLimiter:
    if settings.user_request_limit_store.lower() == USER_REQUEST_LIMIT_STORE_FIRESTORE:
        return FirestoreDailyUserRequestLimiter(
            project_id=settings.gcp_project_id,
            database_id=settings.firestore_database_id,
            collection=settings.firestore_usage_collection,
            limit=settings.daily_user_request_limit,
            timeout_seconds=settings.request_timeout_seconds,
        )

    with _memory_limiter_lock:
        limiter = _memory_limiters_by_limit.get(settings.daily_user_request_limit)
        if limiter is None:
            limiter = DailyUserRequestLimiter(limit=settings.daily_user_request_limit)
            _memory_limiters_by_limit[settings.daily_user_request_limit] = limiter
        return limiter


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
