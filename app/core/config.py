from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.constants import (
    DAILY_USER_REQUEST_LIMIT,
    DEFAULT_USER_REQUEST_LIMIT_STORE,
    FIRESTORE_DATABASE_ID_DEFAULT,
    FIRESTORE_USAGE_COLLECTION,
    GEMINI_MODEL_DEFAULT,
    MAX_IMAGE_BYTES_DEFAULT,
    REQUEST_TIMEOUT_SECONDS_DEFAULT,
)


class Settings(BaseSettings):
    app_env: str = Field(default="local", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    app_log_level: str = Field(default="INFO", alias="APP_LOG_LEVEL")

    line_channel_secret: str = Field(default="", alias="LINE_CHANNEL_SECRET")
    line_channel_access_token: str = Field(
        default="",
        alias="LINE_CHANNEL_ACCESS_TOKEN",
    )
    line_signature_verification_enabled: bool = Field(
        default=True,
        alias="LINE_SIGNATURE_VERIFICATION_ENABLED",
    )

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default=GEMINI_MODEL_DEFAULT, alias="GEMINI_MODEL")

    request_timeout_seconds: int = Field(
        default=REQUEST_TIMEOUT_SECONDS_DEFAULT,
        alias="REQUEST_TIMEOUT_SECONDS",
    )
    max_image_bytes: int = Field(
        default=MAX_IMAGE_BYTES_DEFAULT,
        alias="MAX_IMAGE_BYTES",
    )
    daily_user_request_limit: int = Field(
        default=DAILY_USER_REQUEST_LIMIT,
        alias="DAILY_USER_REQUEST_LIMIT",
    )
    user_request_limit_store: str = Field(
        default=DEFAULT_USER_REQUEST_LIMIT_STORE,
        alias="USER_REQUEST_LIMIT_STORE",
    )
    gcp_project_id: str = Field(default="", alias="GCP_PROJECT_ID")
    firestore_database_id: str = Field(
        default=FIRESTORE_DATABASE_ID_DEFAULT,
        alias="FIRESTORE_DATABASE_ID",
    )
    firestore_usage_collection: str = Field(
        default=FIRESTORE_USAGE_COLLECTION,
        alias="FIRESTORE_USAGE_COLLECTION",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
