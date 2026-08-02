"""Settings unit tests."""

from pytest import MonkeyPatch

from apps.api.config import Settings


def test_settings_read_environment_variables(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "test-api")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_PORT", "9000")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = Settings(_env_file=None)

    assert settings.app_name == "test-api"
    assert settings.app_env == "test"
    assert settings.app_port == 9000
    assert settings.log_level == "DEBUG"


def test_api_host_alias_is_supported(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("APP_HOST", raising=False)
    monkeypatch.setenv("API_HOST", "127.0.0.1")

    assert Settings(_env_file=None).app_host == "127.0.0.1"
