"""Railway API deployment configuration contract tests."""

from __future__ import annotations

import os
import shlex
import subprocess
import tomllib
from pathlib import Path

_ROOT = Path(__file__).parents[2]
_PORT_VARIABLE = "PORT"
_LITERAL_PORT_EXPRESSION = "${PORT:-8000}"


def _railway_api_start_command() -> str:
    config = tomllib.loads((_ROOT / "deploy" / "railway" / "api" / "railway.toml").read_text())
    return config["deploy"]["startCommand"]


def _capture_uvicorn_arguments(
    start_command: str,
    uvicorn_bin_dir: Path,
    port: str | None,
) -> list[str]:
    uvicorn_stub = uvicorn_bin_dir / "uvicorn"
    uvicorn_stub.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
    uvicorn_stub.chmod(0o755)

    environment = os.environ.copy()
    environment["PATH"] = f"{uvicorn_bin_dir}{os.pathsep}{environment['PATH']}"
    if port is None:
        environment.pop(_PORT_VARIABLE, None)
    else:
        environment[_PORT_VARIABLE] = port

    completed = subprocess.run(  # noqa: S603 -- repository-controlled Railway command only
        shlex.split(start_command),
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )
    return completed.stdout.splitlines()


def test_railway_api_start_command_uses_shell_for_port_expansion() -> None:
    assert _railway_api_start_command() == (
        '/bin/sh -c "exec uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"'
    )


def test_railway_api_command_expands_default_port_before_calling_uvicorn(
    tmp_path: Path,
) -> None:
    arguments = _capture_uvicorn_arguments(
        _railway_api_start_command(),
        tmp_path,
        port=None,
    )

    assert arguments[-2:] == ["--port", "8000"]
    assert _LITERAL_PORT_EXPRESSION not in arguments


def test_railway_api_command_preserves_explicit_port_before_calling_uvicorn(
    tmp_path: Path,
) -> None:
    arguments = _capture_uvicorn_arguments(
        _railway_api_start_command(),
        tmp_path,
        port="8080",
    )

    assert arguments[-2:] == ["--port", "8080"]
    assert _LITERAL_PORT_EXPRESSION not in arguments


def test_api_dockerfile_keeps_fixed_local_fallback() -> None:
    dockerfile = (_ROOT / "deploy" / "railway" / "api" / "Dockerfile").read_text()

    assert '"--port", "8000"' in dockerfile
