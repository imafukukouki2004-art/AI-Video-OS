"""Validate AI Video OS production infrastructure without invoking AI or publishing flows.

Dry-run is the default mode. It validates configuration shape and secret presence without
network access or writes. Live checks are opt-in and limited to infrastructure dependencies.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import Literal
from uuid import uuid4

import httpx
from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import ValidationError
from sqlalchemy import text

from apps.api.cache import RedisManager
from apps.api.config import Settings
from apps.api.database import Database
from apps.api.storage import S3ObjectStorage

CheckStatus = Literal[
    "CONFIGURED",
    "MISSING",
    "PASS",
    "FAIL",
    "SKIPPED",
    "UNSAFE",
]

_FALSE_VALUES = {"", "0", "false", "no", "off"}
_PLACEHOLDER_VALUES = {"sk-dummy", "change-me-local-only"}
_SECRET_SETTINGS = (
    "openai_api_key",
    "youtube_client_id",
    "youtube_client_secret",
    "youtube_credential_encryption_key",
)
_CONNECTION_SETTINGS = (
    "database_url",
    "redis_url",
    "celery_broker_url",
    "celery_result_backend",
    "storage_access_key",
    "storage_secret_key",
)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """A non-secret infrastructure validation result."""

    check: str
    status: CheckStatus
    detail: str


def _is_configured(value: str) -> bool:
    """Return whether a value is non-empty and not a repository placeholder."""

    normalized = value.strip().lower()
    return bool(normalized) and not any(token in normalized for token in _PLACEHOLDER_VALUES)


def _secret_presence(settings: Settings) -> list[ValidationResult]:
    """Report configured or missing only; never return a secret value."""

    results: list[ValidationResult] = []
    for setting_name in _SECRET_SETTINGS + _CONNECTION_SETTINGS:
        value = getattr(settings, setting_name).get_secret_value()
        status: CheckStatus = "CONFIGURED" if _is_configured(value) else "MISSING"
        results.append(
            ValidationResult(
                check=setting_name.upper(),
                status=status,
                detail="configured" if status == "CONFIGURED" else "missing or placeholder",
            )
        )
    return results


def dry_run(settings: Settings, environment: dict[str, str]) -> list[ValidationResult]:
    """Validate settings and safety requirements without network access or writes."""

    results = _secret_presence(settings)
    results.extend(
        [
            ValidationResult(
                check="APP_ENV",
                status="PASS" if settings.app_env == "production" else "FAIL",
                detail="production required",
            ),
            ValidationResult(
                check="YOUTUBE_PRIVACY_STATUS",
                status="PASS" if settings.youtube_privacy_status == "private" else "FAIL",
                detail="private required",
            ),
            ValidationResult(
                check="STORAGE_ADDRESSING_STYLE",
                status="PASS" if settings.storage_addressing_style == "virtual" else "FAIL",
                detail="virtual required for Railway Storage Bucket",
            ),
            ValidationResult(
                check="AI_VIDEO_OS_RUN_PRODUCTION_E2E",
                status=(
                    "PASS"
                    if environment.get("AI_VIDEO_OS_RUN_PRODUCTION_E2E", "false").lower()
                    in _FALSE_VALUES
                    else "UNSAFE"
                ),
                detail="must remain disabled before final CEO approval",
            ),
            ValidationResult(
                check="LIVE_NETWORK_ACCESS",
                status="SKIPPED",
                detail="dry-run performs no network access or writes",
            ),
            ValidationResult(
                check="OAUTH_AND_AI_PUBLISHING",
                status="SKIPPED",
                detail="not part of infrastructure validation",
            ),
        ]
    )
    return results


async def _migration_result(database: Database) -> ValidationResult:
    """Read the applied Alembic revision without mutating database state."""

    try:
        async with database.engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        expected_heads = set(ScriptDirectory.from_config(Config("alembic.ini")).get_heads())
    except Exception as error:
        return ValidationResult(
            check="ALEMBIC_MIGRATION",
            status="FAIL",
            detail=f"migration status unavailable ({type(error).__name__})",
        )
    status: CheckStatus = "PASS" if str(revision) in expected_heads else "FAIL"
    return ValidationResult(
        check="ALEMBIC_MIGRATION",
        status=status,
        detail="current" if status == "PASS" else "applied revision is not a repository head",
    )


async def _api_results(api_base_url: str | None) -> list[ValidationResult]:
    """Read API health endpoints only when a base URL is explicitly provided."""

    if not api_base_url:
        return [
            ValidationResult(
                check="API_HEALTH_AND_READINESS",
                status="SKIPPED",
                detail="provide --api-base-url for read-only endpoint checks",
            )
        ]
    results: list[ValidationResult] = []
    try:
        async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
            for path, name in (("/health", "API_HEALTH"), ("/ready", "API_READINESS")):
                response = await client.get(path)
                results.append(
                    ValidationResult(
                        check=name,
                        status="PASS" if response.status_code == 200 else "FAIL",
                        detail=f"HTTP {response.status_code}",
                    )
                )
    except httpx.HTTPError as error:
        results.append(
            ValidationResult(
                check="API_HEALTH_AND_READINESS",
                status="FAIL",
                detail=f"endpoint request failed ({type(error).__name__})",
            )
        )
    return results


async def _storage_probe(
    storage: S3ObjectStorage, check_presigned_access: bool
) -> list[ValidationResult]:
    """Use one temporary key for upload/read/delete and remove it in a finally block."""

    key = f"validation/infrastructure/{uuid4()}.txt"
    body = b"ai-video-os-infrastructure-validation"
    results: list[ValidationResult] = []
    try:
        await storage.upload(key, body, "text/plain")
        results.append(ValidationResult("STORAGE_UPLOAD", "PASS", "temporary object uploaded"))
        downloaded = await storage.download(key)
        read_status: CheckStatus = "PASS" if downloaded.body == body else "FAIL"
        results.append(
            ValidationResult("STORAGE_READ", read_status, "temporary object content verified")
        )
        url = await storage.create_presigned_download_url(key, 60)
        results.append(
            ValidationResult("PRESIGNED_URL_GENERATION", "PASS" if url else "FAIL", "URL generated")
        )
        if check_presigned_access:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
            results.append(
                ValidationResult(
                    "PRESIGNED_URL_ACCESS",
                    "PASS" if response.status_code == 200 else "FAIL",
                    f"HTTP {response.status_code}",
                )
            )
        else:
            results.append(
                ValidationResult(
                    "PRESIGNED_URL_ACCESS",
                    "SKIPPED",
                    "enable --check-presigned-access for an explicit read-only URL request",
                )
            )
    except Exception as error:
        results.append(
            ValidationResult(
                check="STORAGE_PROBE",
                status="FAIL",
                detail=f"storage probe failed ({type(error).__name__})",
            )
        )
    finally:
        try:
            await storage.delete(key)
            results.append(ValidationResult("STORAGE_DELETE", "PASS", "temporary object removed"))
        except Exception as error:
            results.append(
                ValidationResult(
                    check="STORAGE_DELETE",
                    status="FAIL",
                    detail=f"temporary object cleanup failed ({type(error).__name__})",
                )
            )
    return results


async def live_checks(
    settings: Settings,
    *,
    api_base_url: str | None,
    storage_probe: bool,
    check_presigned_access: bool,
) -> list[ValidationResult]:
    """Perform opt-in infrastructure checks only; no AI, OAuth, workflow, or publishing calls."""

    database = Database(settings)
    redis = RedisManager(settings)
    storage = S3ObjectStorage(settings)
    results: list[ValidationResult] = []
    try:
        results.extend(await _api_results(api_base_url))
        results.append(
            ValidationResult(
                "POSTGRESQL_CONNECTIVITY",
                "PASS" if await database.check_connection() else "FAIL",
                "minimal connection query",
            )
        )
        results.append(await _migration_result(database))
        results.append(
            ValidationResult(
                "REDIS_CONNECTIVITY",
                "PASS" if await redis.check_connection() else "FAIL",
                "Redis PING",
            )
        )
        results.append(
            ValidationResult(
                "STORAGE_CONNECTIVITY",
                "PASS" if await storage.check_connection() else "FAIL",
                "Bucket head request",
            )
        )
        if storage_probe:
            results.extend(await _storage_probe(storage, check_presigned_access))
        else:
            results.append(
                ValidationResult(
                    "STORAGE_R_W_DELETE",
                    "SKIPPED",
                    "enable --storage-probe for a temporary-key probe",
                )
            )
    finally:
        await storage.close()
        await redis.close()
        await database.dispose()
    return results


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="validate configuration only; this is the default and performs no network access",
    )
    mode.add_argument(
        "--live",
        action="store_true",
        help=(
            "perform opt-in infrastructure checks only; never calls AI, OAuth, workflow, "
            "or publishing APIs"
        ),
    )
    parser.add_argument("--api-base-url", help="optional API URL for GET /health and GET /ready")
    parser.add_argument(
        "--storage-probe",
        action="store_true",
        help="with --live, upload/read/delete one generated temporary storage key",
    )
    parser.add_argument(
        "--check-presigned-access",
        action="store_true",
        help="with --live --storage-probe, request the generated presigned URL without printing it",
    )
    parser.add_argument("--json", action="store_true", help="emit non-secret JSON results")
    return parser.parse_args()


def _emit(results: list[ValidationResult], as_json: bool) -> None:
    if as_json:
        print(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True))
        return
    for result in results:
        print(f"{result.check}: {result.status} — {result.detail}")


async def _run() -> int:
    args = _parse_args()
    if (args.storage_probe or args.check_presigned_access) and not args.live:
        print("STORAGE_PROBE: UNSAFE — --storage-probe requires explicit --live", file=sys.stderr)
        return 2
    if args.check_presigned_access and not args.storage_probe:
        print(
            "PRESIGNED_URL_ACCESS: UNSAFE — --check-presigned-access requires --storage-probe",
            file=sys.stderr,
        )
        return 2
    try:
        settings = Settings()
    except ValidationError:
        _emit(
            [
                ValidationResult(
                    check="SETTINGS_LOAD",
                    status="FAIL",
                    detail="settings validation failed",
                )
            ],
            args.json,
        )
        return 1
    results = dry_run(settings, dict(os.environ))
    if args.live:
        results.extend(
            await live_checks(
                settings,
                api_base_url=args.api_base_url,
                storage_probe=args.storage_probe,
                check_presigned_access=args.check_presigned_access,
            )
        )
    _emit(results, args.json)
    return 0 if all(result.status not in {"FAIL", "UNSAFE"} for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
