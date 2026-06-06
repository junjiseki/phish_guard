import pytest

from app.core.config import Settings
from app.services.user_request_limiter import (
    DailyUserRequestLimiter,
    FirestoreDailyUserRequestLimiter,
    UserRequestLimiterConfigurationError,
    build_request_limiter,
    parse_firestore_response,
    parse_ndjson_objects,
    resolve_timezone,
)

EXPECTED_LIMIT_COUNT_1 = 1
TEST_DAILY_USER_REQUEST_LIMIT = 2


def test_daily_user_request_limiter_allows_only_configured_count() -> None:
    limiter = DailyUserRequestLimiter(limit=TEST_DAILY_USER_REQUEST_LIMIT)

    assert limiter.allow("user-id")
    assert limiter.allow("user-id")
    assert not limiter.allow("user-id")
    assert limiter.allow("another-user-id")


def test_daily_user_request_limiter_rejects_non_positive_limit() -> None:
    with pytest.raises(UserRequestLimiterConfigurationError):
        DailyUserRequestLimiter(limit=0)


def test_firestore_request_limiter_rejects_invalid_configuration() -> None:
    with pytest.raises(UserRequestLimiterConfigurationError):
        FirestoreDailyUserRequestLimiter(
            project_id="",
            database_id="(default)",
            collection="usage",
            limit=2,
            timeout_seconds=1,
        )

    with pytest.raises(UserRequestLimiterConfigurationError):
        FirestoreDailyUserRequestLimiter(
            project_id="project-id",
            database_id="(default)",
            collection="usage",
            limit=0,
            timeout_seconds=1,
        )

    with pytest.raises(UserRequestLimiterConfigurationError):
        FirestoreDailyUserRequestLimiter(
            project_id="project-id",
            database_id="(default)",
            collection="usage",
            limit=2,
            timeout_seconds=0,
        )


def test_resolve_timezone_falls_back_to_utc_for_unknown_zone() -> None:
    timezone = resolve_timezone("Not/A_Real_Timezone")

    assert timezone.key == "UTC"


def test_parse_ndjson_objects_reads_batch_get_stream() -> None:
    raw_body = (
        '{"found":{"name":"projects/p/databases/(default)/documents/usage/doc",'
        '"fields":{"count":{"integerValue":"1"}}}}\n'
        '{"found":{"name":"projects/p/databases/(default)/documents/usage/doc2",'
        '"fields":{"count":{"integerValue":"2"}}}}\n'
    )

    objects = parse_ndjson_objects(raw_body)

    assert len(objects) == 2
    assert objects[0]["found"]["fields"]["count"]["integerValue"] == "1"


def test_parse_firestore_response_uses_ndjson_for_batch_get() -> None:
    raw_body = (
        '{"found":{"fields":{"count":{"integerValue":"1"}}}}\n'
    )

    response = parse_firestore_response(":batchGet", raw_body)

    assert isinstance(response, list)
    assert response[0]["found"]["fields"]["count"]["integerValue"] == "1"


def test_build_request_limiter_uses_memory_store_by_default() -> None:
    limiter = build_request_limiter(
        Settings(
            USER_REQUEST_LIMIT_STORE="memory",
            DAILY_USER_REQUEST_LIMIT=3,
        ),
    )

    assert isinstance(limiter, DailyUserRequestLimiter)
    assert limiter.limit == 3


def test_build_request_limiter_uses_firestore_store() -> None:
    limiter = build_request_limiter(
        Settings(
            USER_REQUEST_LIMIT_STORE="firestore",
            GCP_PROJECT_ID="project-id",
            DAILY_USER_REQUEST_LIMIT=2,
        ),
    )

    assert isinstance(limiter, FirestoreDailyUserRequestLimiter)


def test_build_request_limiter_rejects_unknown_store() -> None:
    with pytest.raises(UserRequestLimiterConfigurationError):
        build_request_limiter(
            Settings(
                USER_REQUEST_LIMIT_STORE="redis",
                DAILY_USER_REQUEST_LIMIT=2,
            ),
        )


def test_firestore_request_limiter_creates_usage_document() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeFirestoreLimiter(FirestoreDailyUserRequestLimiter):
        def _post_json(self, *, path: str, body: dict[str, object]) -> object:  # type: ignore[override]
            calls.append((path, body))
            if path == ":beginTransaction":
                return {"transaction": "transaction-id"}
            if path == ":batchGet":
                return [{}]
            if path == ":commit":
                return {}
            raise AssertionError(path)

    limiter = FakeFirestoreLimiter(
        project_id="project-id",
        database_id="(default)",
        collection="usage",
        limit=2,
        timeout_seconds=1,
    )

    assert limiter.allow("user-id")
    assert calls[-1][0] == ":commit"
    fields = calls[-1][1]["writes"][0]["update"]["fields"]  # type: ignore[index]
    assert fields["count"] == {"integerValue": str(EXPECTED_LIMIT_COUNT_1)}


def test_firestore_request_limiter_rejects_when_limit_is_reached() -> None:
    calls: list[str] = []

    class FakeFirestoreLimiter(FirestoreDailyUserRequestLimiter):
        def _post_json(self, *, path: str, body: dict[str, object]) -> object:  # type: ignore[override]
            calls.append(path)
            if path == ":beginTransaction":
                return {"transaction": "transaction-id"}
            if path == ":batchGet":
                return [
                    {
                        "found": {
                            "fields": {
                                "count": {"integerValue": "2"},
                            },
                        },
                    },
                ]
            if path == ":rollback":
                return {}
            raise AssertionError(path)

    limiter = FakeFirestoreLimiter(
        project_id="project-id",
        database_id="(default)",
        collection="usage",
        limit=2,
        timeout_seconds=1,
    )

    assert not limiter.allow("user-id")
    assert ":commit" not in calls
    assert calls[-1] == ":rollback"
