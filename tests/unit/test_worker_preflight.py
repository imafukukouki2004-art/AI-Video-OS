"""Tests for TICKET-043 Worker capability preflight."""

from __future__ import annotations

from subprocess import CompletedProcess
from unittest.mock import Mock

from apps.worker import preflight


def test_worker_preflight_runs_only_ffmpeg_version(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    run = Mock(return_value=CompletedProcess(["/usr/bin/ffmpeg", "-version"], 0))
    monkeypatch.setattr(preflight.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    monkeypatch.setattr(preflight.subprocess, "run", run)

    result = preflight.preflight_capabilities()

    assert result["worker"] == "ok"
    assert result["ffmpeg"] == "ok"
    assert set(result) == {"worker", "ffmpeg"}
    run.assert_called_once_with(
        ["/usr/bin/ffmpeg", "-version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )


def test_worker_preflight_does_not_spawn_any_task_when_ffmpeg_is_missing(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    run = Mock()
    monkeypatch.setattr(preflight.shutil, "which", lambda _: None)
    monkeypatch.setattr(preflight.subprocess, "run", run)

    result = preflight.preflight_capabilities()

    assert result == {"worker": "ok", "ffmpeg": "missing"}
    run.assert_not_called()
