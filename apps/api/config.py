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


@lru_cache
def get_settings() -> Settings:
    """Return a process-local immutable-by-convention settings instance."""

    return Settings()
