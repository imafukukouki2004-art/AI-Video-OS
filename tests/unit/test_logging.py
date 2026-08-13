"""Structured logging unit tests."""

import json
import logging

from pytest import CaptureFixture

from apps.api.config import Settings
from apps.api.logging import configure_logging, get_logger


def test_json_log_contains_required_fields(capsys: CaptureFixture[str]) -> None:
    settings = Settings(app_env="test", log_format="json", _env_file=None)
    configure_logging(settings, force=True)

    get_logger().info("test_event", request_id="request-123")

    event = json.loads(capsys.readouterr().out)
    assert event["timestamp"]
    assert event["level"] == "info"
    assert event["service"] == "ai-video-os-api"
    assert event["environment"] == "test"
    assert event["message"] == "test_event"
    assert event["request_id"] == "request-123"
    assert logging.getLogger("uvicorn.access").disabled is True
