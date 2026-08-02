"""Idempotent structlog configuration."""

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog
from structlog.typing import EventDict, Processor

from apps.api.config import Settings

_is_configured = False


def _add_application_context(settings: Settings) -> Processor:
    def processor(
        _logger: Any,
        _method_name: str,
        event_dict: EventDict,
    ) -> EventDict:
        event_dict.setdefault("service", settings.app_name)
        event_dict.setdefault("environment", settings.app_env)
        event = event_dict.get("event")
        if event is not None:
            event_dict.setdefault("message", event)
        event_dict.setdefault("request_id", None)
        return event_dict

    return processor


def configure_logging(settings: Settings, *, force: bool = False) -> None:
    """Configure standard logging and structlog without duplicate handlers."""

    global _is_configured
    if _is_configured and not force:
        return

    renderer: Processor
    if settings.log_format == "console":
        renderer = structlog.dev.ConsoleRenderer(colors=False)
    else:
        renderer = structlog.processors.JSONRenderer()

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
        force=True,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
            _add_application_context(settings),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.log_level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _is_configured = True


def get_logger() -> structlog.stdlib.BoundLogger:
    """Return a structured logger."""

    return structlog.get_logger()  # type: ignore[no-any-return]


def sanitize_event(event: MutableMapping[str, Any]) -> dict[str, Any]:
    """Keep this boundary explicit: callers must never log secrets or request bodies."""

    return dict(event)
