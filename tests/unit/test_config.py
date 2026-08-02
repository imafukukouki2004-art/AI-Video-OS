"""Settings unit tests."""

from pytest import MonkeyPatch

from apps.api.config import Settings


def test_settings_read_environment_variables(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "test-api")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_PORT", "9000")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://test-user:test-password@database:5432/test-db",
    )
    monkeypatch.setenv("REDIS_URL", "redis://:redis-password@cache:6379/0")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://:broker-password@cache:6379/0")

    settings = Settings(_env_file=None)

    assert settings.app_name == "test-api"
    assert settings.app_env == "test"
    assert settings.app_port == 9000
    assert settings.log_level == "DEBUG"
    assert settings.database_url.get_secret_value().endswith("@database:5432/test-db")
    assert "test-password" not in repr(settings)
    assert settings.redis_url.get_secret_value().endswith("@cache:6379/0")
    assert "redis-password" not in repr(settings)
    assert "broker-password" not in repr(settings)


def test_api_host_alias_is_supported(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("APP_HOST", raising=False)
    monkeypatch.setenv("API_HOST", "127.0.0.1")

    assert Settings(_env_file=None).app_host == "127.0.0.1"
