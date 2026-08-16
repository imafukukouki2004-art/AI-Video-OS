"""Environment-backed application settings."""

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "ai-video-os-api"
    app_env: Literal["development", "test", "production"] = "development"
    app_version: str = "0.1.0"
    app_host: str = Field(
        default="0.0.0.0",  # noqa: S104 - required container bind address
        validation_alias=AliasChoices("APP_HOST", "API_HOST"),
    )
    app_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("APP_PORT", "API_PORT"),
    )
    app_debug: bool = False
    log_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"
    log_format: Literal["json", "console"] = "json"
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://ai_video_os:change-me-local-only@127.0.0.1:5432/ai_video_os"
    )
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=100)
    database_pool_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    database_connect_timeout_seconds: int = Field(default=3, ge=1, le=30)
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")
    redis_connect_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    redis_socket_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    celery_broker_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")
    celery_result_backend: SecretStr = SecretStr("redis://127.0.0.1:6379/1")
    celery_task_max_retries: int = Field(default=3, ge=0, le=20)
    celery_retry_backoff_max_seconds: int = Field(default=60, ge=1, le=3600)
    storage_endpoint_url: str = "http://127.0.0.1:9000"
    storage_access_key: SecretStr = Field(default_factory=lambda: SecretStr(""))
    storage_secret_key: SecretStr = Field(default_factory=lambda: SecretStr(""))
    storage_bucket: str = Field(default="ai-video-os-assets", pattern=r"^[a-z0-9][a-z0-9.-]+$")
    storage_region: str = "us-east-1"
    storage_addressing_style: Literal["path", "virtual"] = "path"
    storage_max_upload_bytes: int = Field(default=26_214_400, ge=1, le=1_073_741_824)
    storage_presigned_expiry_seconds: int = Field(default=900, ge=60, le=604_800)
    storage_connect_timeout_seconds: int = Field(default=3, ge=1, le=30)
    storage_read_timeout_seconds: int = Field(default=10, ge=1, le=120)
    openai_api_key: SecretStr = Field(default_factory=lambda: SecretStr("sk-dummy"))
    openai_model: str = "gpt-4o"
    youtube_client_id: SecretStr = Field(default_factory=lambda: SecretStr(""))
    youtube_client_secret: SecretStr = Field(default_factory=lambda: SecretStr(""))
    youtube_refresh_token: SecretStr = Field(default_factory=lambda: SecretStr(""))
    youtube_privacy_status: Literal["private", "unlisted", "public"] = "private"
    youtube_oauth_redirect_uri: str = (
        "http://localhost:8000/publishing/connections/youtube/callback"
    )
    youtube_oauth_state_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    youtube_credential_encryption_key: SecretStr = Field(default_factory=lambda: SecretStr(""))


@lru_cache
def get_settings() -> Settings:
    """Return a process-local immutable-by-convention settings instance."""

    return Settings()
