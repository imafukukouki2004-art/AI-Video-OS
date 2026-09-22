"""Secret-free Worker capability probe used by Production Preflight."""

from __future__ import annotations

import shutil
import subprocess
from typing import TypedDict

from apps.worker.celery_app import celery_app


class WorkerPreflightResult(TypedDict):
    worker: str
    ffmpeg: str


@celery_app.task(name="apps.worker.preflight.capabilities")  # type: ignore[misc]
def preflight_capabilities() -> WorkerPreflightResult:
    """Verify the Worker can execute a task and invoke FFmpeg without external APIs."""

    executable = shutil.which("ffmpeg")
    if executable is None:
        return {"worker": "ok", "ffmpeg": "missing"}

    try:
        completed = subprocess.run(  # noqa: S603
            [executable, "-version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return {"worker": "ok", "ffmpeg": "failed"}

    return {
        "worker": "ok",
        "ffmpeg": "ok" if completed.returncode == 0 else "failed",
    }
