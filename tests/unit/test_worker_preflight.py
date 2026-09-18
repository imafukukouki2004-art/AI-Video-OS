"""Tests for TICKET-043 Worker capability preflight."""

from __future__ import annotations

from apps.worker.preflight import preflight_capabilities


def test_worker_preflight_reports_worker_and_ffmpeg_without_secrets() -> None:
    result = preflight_capabilities()

    assert result["worker"] == "ok"
    assert result["ffmpeg"] in {"ok", "missing", "failed"}
    assert set(result) == {"worker", "ffmpeg"}
