"""Request identifiers and structured access logging."""

import re
from time import perf_counter
from uuid import uuid4

import structlog.contextvars
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from apps.api.logging import get_logger

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _request_id_from_header(value: str | None) -> str:
    if value is not None and _SAFE_REQUEST_ID.fullmatch(value):
        return value
    return str(uuid4())


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a safe request ID and emit request lifecycle logs."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = _request_id_from_header(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        logger = get_logger()
        started_at = perf_counter()

        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
        )
        try:
            response = await call_next(request)
            duration_ms = round((perf_counter() - started_at) * 1000, 3)
            response.headers[REQUEST_ID_HEADER] = request_id
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            return response
        except Exception:
            duration_ms = round((perf_counter() - started_at) * 1000, 3)
            # Do not serialize exception text: it can contain credentials or user data.
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                error_code="INTERNAL_SERVER_ERROR",
            )
            raise
        finally:
            structlog.contextvars.clear_contextvars()
