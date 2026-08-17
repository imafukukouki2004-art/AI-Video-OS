"""Unit tests for the safe production infrastructure validator."""

from __future__ import annotations

import asyncio
import runpy
from pathlib import Path
from typing import Any

from apps.api.config import Settings
from apps.api.storage import StoredObject

_VALIDATOR_PATH = Path(__file__).parents[2] / "scripts" / "validate_production_infrastructure.py"
_VALIDATOR = runpy.run_path(str(_VALIDATOR_PATH), run_name="infrastructure_validator")


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
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_dry_run_reports_configuration_without_secret_values() -> None:
    dry_run = _VALIDATOR["dry_run"]

    results = dry_run(_production_settings(), {"AI_VIDEO_OS_RUN_PRODUCTION_E2E": "false"})
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
        {"AI_VIDEO_OS_RUN_PRODUCTION_E2E": "true"},
    )
    by_check = {result.check: result for result in results}

    assert by_check["STORAGE_ADDRESSING_STYLE"].status == "FAIL"
    assert by_check["AI_VIDEO_OS_RUN_PRODUCTION_E2E"].status == "UNSAFE"


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
