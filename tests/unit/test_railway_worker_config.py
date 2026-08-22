"""Railway Worker deployment configuration contract tests."""

from __future__ import annotations

import os
import shlex
import subprocess
import tomllib
from pathlib import Path

_ROOT = Path(__file__).parents[2]
_CONCURRENCY_VARIABLE = "CELERY_WORKER_CONCURRENCY"
_LITERAL_CONCURRENCY_EXPRESSION = "${CELERY_WORKER_CONCURRENCY:-2}"


def _railway_worker_start_command() -> str:
    config = tomllib.loads((_ROOT / "deploy" / "railway" / "worker" / "railway.toml").read_text())
    return config["deploy"]["startCommand"]


def _capture_celery_arguments(
    start_command: str,
    celery_bin_dir: Path,
    concurrency: str | None,
) -> list[str]:
    celery_stub = celery_bin_dir / "celery"
    celery_stub.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
    celery_stub.chmod(0o755)

    environment = os.environ.copy()
    environment["PATH"] = f"{celery_bin_dir}{os.pathsep}{environment['PATH']}"
    if concurrency is None:
        environment.pop(_CONCURRENCY_VARIABLE, None)
    else:
        environment[_CONCURRENCY_VARIABLE] = concurrency

    completed = subprocess.run(  # noqa: S603 -- repository-controlled railway.toml command only
        shlex.split(start_command),
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )
    return completed.stdout.splitlines()


def test_railway_worker_start_command_uses_shell_for_bounded_concurrency() -> None:
    start_command = _railway_worker_start_command()

    assert start_command == (
        '/bin/sh -c "exec celery -A apps.worker.celery_app:celery_app worker '
        '--loglevel=INFO --concurrency=${CELERY_WORKER_CONCURRENCY:-2}"'
    )


def test_railway_worker_command_expands_default_concurrency_before_calling_celery(
    tmp_path: Path,
) -> None:
    arguments = _capture_celery_arguments(
        _railway_worker_start_command(),
        tmp_path,
        concurrency=None,
    )

    assert arguments[-1] == "--concurrency=2"
    assert _LITERAL_CONCURRENCY_EXPRESSION not in arguments


def test_railway_worker_command_preserves_configurable_concurrency_before_calling_celery(
    tmp_path: Path,
) -> None:
    arguments = _capture_celery_arguments(
        _railway_worker_start_command(),
        tmp_path,
        concurrency="4",
    )

    assert arguments[-1] == "--concurrency=4"
    assert _LITERAL_CONCURRENCY_EXPRESSION not in arguments


def test_worker_dockerfile_keeps_safe_fallback_for_non_railway_execution() -> None:
    dockerfile = (_ROOT / "apps" / "worker" / "Dockerfile").read_text()

    assert '"--concurrency=2"' in dockerfile
