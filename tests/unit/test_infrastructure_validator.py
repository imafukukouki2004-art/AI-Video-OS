"""Unit tests for the safe production infrastructure validator."""

from __future__ import annotations

import asyncio
import json
import runpy
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from apps.api.config import Settings
from apps.api.publishing.credentials import CredentialResolutionError
from apps.api.storage import StoredObject

_VALIDATOR_PATH = Path(__file__).parents[2] / "scripts" / "validate_production_infrastructure.py"
_VALIDATOR = runpy.run_path(str(_VALIDATOR_PATH), run_name="infrastructure_validator")
_GLOBALS = _VALIDATOR["dry_run"].__globals__


def _production_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "production",
        "storage_addressing_style": "virtual",
        "youtube_privacy_status": "private",
        "database_url": "postgresql+psycopg://user:password@db.example:5432/app",
        "redis_url": "redis://redis.example:6379/0",
        "celery_broker_url": "redis://redis.example:6379/0",
        "celery_result_backend": "redis://redis.example:6379/1",
        "storage_access_key": "access-key",
        "storage_secret_key": "secret-key",
        "openai_api_key": "configured-openai-key",
        "youtube_client_id": "configured-client-id",
        "youtube_client_secret": "configured-client-secret",
        "youtube_credential_encryption_key": "configured-encryption-key",
        "youtube_oauth_redirect_uri": (
            "https://api.example.test/publishing/connections/youtube/callback"
        ),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_dry_run_reports_configuration_without_secret_values() -> None:
    dry_run = _VALIDATOR["dry_run"]

    results = dry_run(
        _production_settings(),
        {
            "AI_VIDEO_OS_RUN_PRODUCTION_E2E": "false",
            "AI_VIDEO_OS_PRODUCTION_E2E_PROJECT_ID": str(uuid4()),
        },
    )
    rendered = "\n".join(f"{result.check}:{result.detail}" for result in results)

    assert all(result.status != "FAIL" for result in results)
    assert "configured-openai-key" not in rendered
    assert "configured-client-secret" not in rendered
    assert "configured-encryption-key" not in rendered
    assert "LIVE_NETWORK_ACCESS:dry-run performs no network access or writes" in rendered
    assert "OAUTH_AND_AI_PUBLISHING:not part of infrastructure validation" in rendered


def test_dry_run_detects_unsafe_production_gate_and_storage_mode() -> None:
    dry_run = _VALIDATOR["dry_run"]

    results = dry_run(
        _production_settings(storage_addressing_style="path"),
        {
            "AI_VIDEO_OS_RUN_PRODUCTION_E2E": "true",
            "AI_VIDEO_OS_PRODUCTION_E2E_PROJECT_ID": str(uuid4()),
        },
    )
    by_check = {result.check: result for result in results}

    assert by_check["STORAGE_ADDRESSING_STYLE"].status == "FAIL"
    assert by_check["AI_VIDEO_OS_RUN_PRODUCTION_E2E"].status == "UNSAFE"


def test_dry_run_does_not_construct_network_clients_or_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def prohibited(*args: object, **kwargs: object) -> None:
        raise AssertionError("dry-run attempted network or persistence access")

    for name in ("Database", "RedisManager", "S3ObjectStorage"):
        monkeypatch.setitem(_GLOBALS, name, prohibited)
    monkeypatch.setattr(_GLOBALS["httpx"], "AsyncClient", prohibited)

    results = _VALIDATOR["dry_run"](
        _production_settings(),
        {
            "AI_VIDEO_OS_RUN_PRODUCTION_E2E": "false",
            "AI_VIDEO_OS_PRODUCTION_E2E_PROJECT_ID": str(uuid4()),
        },
    )

    assert all(result.status not in {"FAIL", "UNSAFE"} for result in results)


def test_json_report_does_not_expose_any_configured_secret(
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _production_settings(
        database_url="postgresql+psycopg://secret-user:secret-password@db.example/app",
        redis_url="redis://:secret-redis@redis.example/0",
        celery_broker_url="redis://:secret-broker@redis.example/0",
        celery_result_backend="redis://:secret-result@redis.example/1",
        storage_access_key="secret-storage-access",
        storage_secret_key="-".join(("secret", "storage", "key")),
    )
    results = _VALIDATOR["dry_run"](
        settings,
        {
            "AI_VIDEO_OS_RUN_PRODUCTION_E2E": "false",
            "AI_VIDEO_OS_PRODUCTION_E2E_PROJECT_ID": str(uuid4()),
        },
    )

    _VALIDATOR["_emit"](results, True)
    report = capsys.readouterr().out
    json.loads(report)
    for secret in (
        "configured-openai-key",
        "configured-client-id",
        "configured-client-secret",
        "configured-encryption-key",
        "secret-user",
        "secret-password",
        "secret-redis",
        "secret-broker",
        "secret-result",
        "secret-storage-access",
        "secret-storage-key",
    ):
        assert secret not in report


class _SessionContext:
    def __init__(self, session: AsyncMock) -> None:
        self.session = session

    async def __aenter__(self) -> AsyncMock:
        return self.session

    async def __aexit__(self, *args: object) -> None:
        return None


class _FakeDatabase:
    def __init__(self, session: AsyncMock) -> None:
        self.session = session

    def session_factory(self) -> _SessionContext:
        return _SessionContext(self.session)


def test_project_existence_check_is_read_only() -> None:
    session = AsyncMock()
    session.scalar.return_value = object()

    result = asyncio.run(_VALIDATOR["_project_result"](_FakeDatabase(session), str(uuid4())))

    assert result.status == "PASS"
    session.scalar.assert_awaited_once()
    session.commit.assert_not_awaited()
    session.flush.assert_not_awaited()


def test_youtube_credential_check_is_local_and_requires_upload_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = SimpleNamespace(scopes=["https://www.googleapis.com/auth/youtube.upload"])
    connection_repository = SimpleNamespace(get_active=AsyncMock(return_value=connection))
    credential_repository = SimpleNamespace()
    resolver = SimpleNamespace(resolve=AsyncMock(return_value=object()))
    session = AsyncMock()

    monkeypatch.setitem(
        _GLOBALS,
        "PublishingConnectionRepository",
        lambda _: connection_repository,
    )
    monkeypatch.setitem(
        _GLOBALS,
        "PublishingCredentialRepository",
        lambda _: credential_repository,
    )
    monkeypatch.setitem(_GLOBALS, "YouTubeCredentialResolver", lambda *args: resolver)
    monkeypatch.setattr(
        _GLOBALS["httpx"],
        "AsyncClient",
        Mock(side_effect=AssertionError("Google API access is prohibited")),
    )

    results = asyncio.run(
        _VALIDATOR["_youtube_credential_results"](
            _FakeDatabase(session),
            _production_settings(),
        )
    )
    by_check = {result.check: result for result in results}

    assert by_check["YOUTUBE_CONNECTION"].status == "PASS"
    assert by_check["YOUTUBE_UPLOAD_SCOPE"].status == "PASS"
    assert by_check["YOUTUBE_OAUTH_CREDENTIAL"].status == "PASS"
    resolver.resolve.assert_awaited_once()
    session.commit.assert_not_awaited()


def test_youtube_credential_decryption_failure_is_secret_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = SimpleNamespace(scopes=["https://www.googleapis.com/auth/youtube.upload"])
    connection_repository = SimpleNamespace(get_active=AsyncMock(return_value=connection))
    resolver = SimpleNamespace(
        resolve=AsyncMock(side_effect=CredentialResolutionError("sensitive-token"))
    )
    monkeypatch.setitem(
        _GLOBALS,
        "PublishingConnectionRepository",
        lambda _: connection_repository,
    )
    monkeypatch.setitem(
        _GLOBALS,
        "PublishingCredentialRepository",
        lambda _: SimpleNamespace(),
    )
    monkeypatch.setitem(_GLOBALS, "YouTubeCredentialResolver", lambda *args: resolver)

    results = asyncio.run(
        _VALIDATOR["_youtube_credential_results"](
            _FakeDatabase(AsyncMock()),
            _production_settings(),
        )
    )
    rendered = json.dumps(
        [result.__dict__ if hasattr(result, "__dict__") else result.detail for result in results]
    )

    assert {result.check: result.status for result in results}["YOUTUBE_OAUTH_CREDENTIAL"] == "FAIL"
    assert "sensitive-token" not in rendered


def test_youtube_credential_check_fails_when_upload_scope_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection_repository = SimpleNamespace(
        get_active=AsyncMock(return_value=SimpleNamespace(scopes=[]))
    )
    resolver = SimpleNamespace(resolve=AsyncMock(return_value=object()))
    monkeypatch.setitem(
        _GLOBALS,
        "PublishingConnectionRepository",
        lambda _: connection_repository,
    )
    monkeypatch.setitem(
        _GLOBALS,
        "PublishingCredentialRepository",
        lambda _: SimpleNamespace(),
    )
    monkeypatch.setitem(_GLOBALS, "YouTubeCredentialResolver", lambda *args: resolver)

    results = asyncio.run(
        _VALIDATOR["_youtube_credential_results"](
            _FakeDatabase(AsyncMock()),
            _production_settings(),
        )
    )

    assert {result.check: result.status for result in results}["YOUTUBE_UPLOAD_SCOPE"] == "FAIL"


def test_worker_probe_dispatches_only_the_capability_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = SimpleNamespace(get=Mock(return_value={"worker": "ok", "ffmpeg": "ok"}))
    app = SimpleNamespace(send_task=Mock(return_value=task))
    import apps.worker.celery_app as celery_module

    monkeypatch.setattr(celery_module, "create_celery_app", lambda _: app)

    results = asyncio.run(_VALIDATOR["_worker_result"](_production_settings()))

    assert all(result.status == "PASS" for result in results)
    app.send_task.assert_called_once_with(
        "apps.worker.preflight.capabilities",
        queue="ai-video-os",
    )
    dispatched_name = app.send_task.call_args.args[0]
    assert "workflow" not in dispatched_name
    assert "publication" not in dispatched_name


def test_external_provider_checks_are_not_checkable() -> None:
    results = _VALIDATOR["_not_checkable_results"]()

    assert results
    assert all(result.status == "NOT_CHECKABLE" for result in results)
    assert {result.check for result in results} == {
        "OPENAI_TEXT_GENERATION_ACCESS",
        "GPT_IMAGE_GENERATION_ACCESS",
        "OPENAI_QUOTA_AND_BILLING",
        "YOUTUBE_TOKEN_REMOTE_VALIDITY",
        "YOUTUBE_UPLOAD_ACCESS",
    }


def test_safe_live_default_checks_storage_without_writing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDatabase:
        async def check_connection(self) -> bool:
            return True

        async def dispose(self) -> None:
            return None

    class FakeRedis:
        async def check_connection(self) -> bool:
            return True

        async def close(self) -> None:
            return None

    class FakeStorage:
        def __init__(self) -> None:
            self.upload = AsyncMock(side_effect=AssertionError("Storage write is prohibited"))

        async def check_connection(self) -> bool:
            return True

        async def close(self) -> None:
            return None

    storage = FakeStorage()
    validation_result = _GLOBALS["ValidationResult"]
    monkeypatch.setitem(_GLOBALS, "Database", lambda _: FakeDatabase())
    monkeypatch.setitem(_GLOBALS, "RedisManager", lambda _: FakeRedis())
    monkeypatch.setitem(_GLOBALS, "S3ObjectStorage", lambda _: storage)
    monkeypatch.setitem(_GLOBALS, "_api_results", AsyncMock(return_value=[]))
    monkeypatch.setitem(
        _GLOBALS,
        "_migration_result",
        AsyncMock(return_value=validation_result("ALEMBIC_MIGRATION", "PASS", "current")),
    )
    monkeypatch.setitem(
        _GLOBALS,
        "_project_result",
        AsyncMock(return_value=validation_result("PRODUCTION_E2E_PROJECT", "PASS", "found")),
    )
    monkeypatch.setitem(
        _GLOBALS,
        "_youtube_credential_results",
        AsyncMock(
            return_value=[
                validation_result("YOUTUBE_CONNECTION", "PASS", "connected"),
                validation_result("YOUTUBE_UPLOAD_SCOPE", "PASS", "present"),
                validation_result("YOUTUBE_OAUTH_CREDENTIAL", "PASS", "resolved"),
            ]
        ),
    )
    monkeypatch.setitem(
        _GLOBALS,
        "_worker_result",
        AsyncMock(
            return_value=[
                validation_result("WORKER_EXECUTION", "PASS", "completed"),
                validation_result("FFMPEG", "PASS", "available"),
            ]
        ),
    )
    storage_probe = AsyncMock()
    monkeypatch.setitem(_GLOBALS, "_storage_probe", storage_probe)

    results = asyncio.run(
        _VALIDATOR["live_checks"](
            _production_settings(),
            api_base_url=None,
            storage_probe=False,
            check_presigned_access=False,
            environment={"AI_VIDEO_OS_PRODUCTION_E2E_PROJECT_ID": str(uuid4())},
        )
    )

    storage.upload.assert_not_awaited()
    storage_probe.assert_not_awaited()
    assert {result.check: result.status for result in results}["STORAGE_CONNECTIVITY"] == "PASS"
    assert {result.check: result.status for result in results}["STORAGE_R_W_DELETE"] == "SKIPPED"


class _FakeStorage:
    def __init__(self) -> None:
        self.uploaded_key: str | None = None
        self.deleted_key: str | None = None

    async def upload(self, key: str, body: bytes, content_type: str) -> None:
        self.uploaded_key = key
        assert body == b"ai-video-os-infrastructure-validation"
        assert content_type == "text/plain"

    async def download(self, key: str) -> StoredObject:
        assert key == self.uploaded_key
        return StoredObject(
            body=b"ai-video-os-infrastructure-validation",
            content_type="text/plain",
        )

    async def delete(self, key: str) -> None:
        self.deleted_key = key

    async def create_presigned_download_url(self, key: str, expires_in: int) -> str:
        assert key == self.uploaded_key
        assert expires_in == 60
        return "https://storage.invalid/temporary-validation-object"


def test_storage_probe_uses_and_removes_a_generated_temporary_key() -> None:
    storage_probe = _VALIDATOR["_storage_probe"]
    storage = _FakeStorage()

    results = asyncio.run(storage_probe(storage, check_presigned_access=False))
    by_check = {result.check: result for result in results}

    assert storage.uploaded_key is not None
    assert storage.uploaded_key.startswith("validation/infrastructure/")
    assert storage.deleted_key == storage.uploaded_key
    assert by_check["STORAGE_UPLOAD"].status == "PASS"
    assert by_check["STORAGE_READ"].status == "PASS"
    assert by_check["STORAGE_DELETE"].status == "PASS"
    assert by_check["PRESIGNED_URL_ACCESS"].status == "SKIPPED"


class _FailingReadStorage(_FakeStorage):
    async def download(self, key: str) -> StoredObject:
        raise RuntimeError("simulated read failure")


def test_storage_probe_cleans_up_temporary_key_after_probe_failure() -> None:
    storage_probe = _VALIDATOR["_storage_probe"]
    storage = _FailingReadStorage()

    results = asyncio.run(storage_probe(storage, check_presigned_access=False))
    by_check = {result.check: result for result in results}

    assert storage.uploaded_key is not None
    assert storage.deleted_key == storage.uploaded_key
    assert by_check["STORAGE_PROBE"].status == "FAIL"
    assert by_check["STORAGE_DELETE"].status == "PASS"
