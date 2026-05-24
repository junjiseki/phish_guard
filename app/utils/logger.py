"""構造化ログの初期化（Cloud Logging 対応、ローカルは JSON 標準出力）。"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

SERVICE_NAME = "phish-guard-api"
SERVICE_VERSION = "0.1.0"


class JsonFormatter(logging.Formatter):
    """Cloud Logging 互換の JSON フォーマッタ。"""

    def __init__(
        self,
        *,
        service: str,
        environment: str,
        version: str,
    ) -> None:
        super().__init__()
        self.service = service
        self.environment = environment
        self.version = version

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service,
            "environment": self.environment,
            "version": self.version,
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        context = getattr(record, "context", None)
        if context is not None:
            payload["context"] = context

        for key, value in record.__dict__.items():
            if key.startswith("_") or key in logging.LogRecord.__dict__:
                continue
            if key in {
                "name",
                "msg",
                "args",
                "created",
                "relativeCreated",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "pathname",
                "filename",
                "module",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "context",
                "taskName",
            }:
                continue
            payload[key] = value

        return json.dumps(payload, ensure_ascii=False)


def setup_logging(
    *,
    app_env: str,
    service_name: str = SERVICE_NAME,
    log_level: str = "INFO",
    service_version: str = SERVICE_VERSION,
    labels: dict[str, str] | None = None,
) -> None:
    """アプリ起動前に 1 度だけ呼び出し、ルートロガーを構成する。"""
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level.upper())

    handler: logging.Handler | None = None
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            JsonFormatter(
                service=service_name, environment=app_env, version=service_version
            )
        )

    root_logger.addHandler(handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    logging.getLogger("httpx").setLevel(logging.WARNING)
