from app.core.config import Settings
from app.services.user_request_limiter import (
    DAILY_USER_REQUEST_LIMIT,
    DailyUserRequestLimiter,
    FirestoreDailyUserRequestLimiter,
    build_request_limiter,
)

EXPECTED_LIMIT_COUNT_1 = 1


def test_daily_user_request_limiter_allows_only_configured_count() -> None:
    limiter = DailyUserRequestLimiter(limit=DAILY_USER_REQUEST_LIMIT)

    assert limiter.allow("user-id")
    assert limiter.allow("user-id")
    assert not limiter.allow("user-id")
    assert limiter.allow("another-user-id")


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
