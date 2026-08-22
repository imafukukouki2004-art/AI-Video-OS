"""Railway Worker deployment configuration contract tests."""

from __future__ import annotations

import tomllib
from pathlib import Path

_ROOT = Path(__file__).parents[2]


def test_railway_worker_start_command_uses_bounded_concurrency() -> None:
    config = tomllib.loads((_ROOT / "deploy" / "railway" / "worker" / "railway.toml").read_text())
    start_command = config["deploy"]["startCommand"]

    assert start_command == (
        "celery -A apps.worker.celery_app:celery_app worker --loglevel=INFO "
        "--concurrency=${CELERY_WORKER_CONCURRENCY:-2}"
    )


def test_worker_dockerfile_keeps_safe_fallback_for_non_railway_execution() -> None:
    dockerfile = (_ROOT / "apps" / "worker" / "Dockerfile").read_text()

    assert '"--concurrency=2"' in dockerfile
