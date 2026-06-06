"""ユーザーごとの日次リクエスト制限。"""

import hashlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Any, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import Settings

logger = logging.getLogger(__name__)

DAILY_USER_REQUEST_LIMIT = 10
DAILY_USER_REQUEST_LIMIT_TIMEZONE = "Asia/Tokyo"
USER_REQUEST_LIMIT_STORE_MEMORY = "memory"
USER_REQUEST_LIMIT_STORE_FIRESTORE = "firestore"
FIRESTORE_API_BASE_URL = "https://firestore.googleapis.com/v1"
FIRESTORE_BATCH_GET_PATH = ":batchGet"
GCP_METADATA_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/"
    "service-accounts/default/token"
)


class UserRequestLimiterError(Exception):
    """リクエスト制限まわりのエラー。"""


class UserRequestLimiterConfigurationError(UserRequestLimiterError):
    """リクエスト制限の設定または外部ストア接続エラー。"""


class UserRequestLimiter(Protocol):
    def allow(self, user_id: str) -> bool: ...


@dataclass
class UserRequestUsage:
    used_on: str
    count: int


def validate_positive_limit(limit: int) -> int:
    if limit <= 0:
        raise UserRequestLimiterConfigurationError(
            "daily_user_request_limit must be a positive integer",
        )
    return limit


def validate_positive_timeout(timeout_seconds: int) -> int:
    if timeout_seconds <= 0:
        raise UserRequestLimiterConfigurationError(
            "request_timeout_seconds must be a positive integer",
        )
    return timeout_seconds


def resolve_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        logger.warning(
            "Timezone %s is unavailable; falling back to UTC",
            timezone_name,
        )
        return ZoneInfo("UTC")


def parse_firestore_response(path: str, raw_body: str) -> Any:
    if path == FIRESTORE_BATCH_GET_PATH:
        return parse_ndjson_objects(raw_body)
    return json.loads(raw_body)


def parse_ndjson_objects(raw_body: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for line in raw_body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if not isinstance(payload, dict):
            raise UserRequestLimiterConfigurationError
        objects.append(payload)
    return objects


class DailyUserRequestLimiter:
    def __init__(
        self,
        limit: int = DAILY_USER_REQUEST_LIMIT,
        timezone_name: str = DAILY_USER_REQUEST_LIMIT_TIMEZONE,
    ) -> None:
        self.limit = validate_positive_limit(limit)
        self.timezone = resolve_timezone(timezone_name)
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
            raise UserRequestLimiterConfigurationError

        self.project_id = project_id
        self.database_id = database_id
        self.collection = collection
        self.limit = validate_positive_limit(limit)
        self.timeout_seconds = validate_positive_timeout(timeout_seconds)
        self.timezone = resolve_timezone(timezone_name)
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
            raise UserRequestLimiterConfigurationError
        return transaction

    def _lookup_document(
        self,
        *,
        document_name: str,
        transaction: str,
    ) -> dict[str, Any] | None:
        response = self._post_json(
            path=FIRESTORE_BATCH_GET_PATH,
            body={
                "documents": [document_name],
                "transaction": transaction,
            },
        )

        if not isinstance(response, list):
            raise UserRequestLimiterConfigurationError

        if not response:
            return None

        first_response = response[0]
        found = first_response.get("found")
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
        except UserRequestLimiterError:
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
                raw_body = response.read().decode("utf-8")
                return parse_firestore_response(path, raw_body)
        except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            raise UserRequestLimiterConfigurationError from exc
        except json.JSONDecodeError as exc:
            raise UserRequestLimiterConfigurationError from exc

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
                raise UserRequestLimiterConfigurationError from exc

            access_token = payload.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise UserRequestLimiterConfigurationError

            expires_in = payload.get("expires_in")
            if not isinstance(expires_in, int):
                expires_in = 300

            self._access_token = access_token
            self._access_token_expires_at = time.monotonic() + max(expires_in - 60, 1)
            return access_token


def build_request_limiter(settings: Settings) -> UserRequestLimiter:
    store = settings.user_request_limit_store.lower()
    limit = validate_positive_limit(settings.daily_user_request_limit)

    if store == USER_REQUEST_LIMIT_STORE_FIRESTORE:
        return FirestoreDailyUserRequestLimiter(
            project_id=settings.gcp_project_id,
            database_id=settings.firestore_database_id,
            collection=settings.firestore_usage_collection,
            limit=limit,
            timeout_seconds=validate_positive_timeout(settings.request_timeout_seconds),
        )

    if store == USER_REQUEST_LIMIT_STORE_MEMORY:
        with _memory_limiter_lock:
            limiter = _memory_limiters_by_limit.get(limit)
            if limiter is None:
                limiter = DailyUserRequestLimiter(limit=limit)
                _memory_limiters_by_limit[limit] = limiter
            return limiter

    raise UserRequestLimiterConfigurationError(
        f"Unknown user_request_limit_store: {settings.user_request_limit_store}",
    )
