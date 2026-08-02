"""FastAPI exception handlers with a stable public contract."""

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from apps.api.errors.exceptions import ApplicationError
from apps.api.errors.responses import error_response, get_request_id
from apps.api.logging import get_logger


async def application_error_handler(
    request: Request,
    exc: ApplicationError,
) -> JSONResponse:
    get_logger().warning(exc.message, error_code=exc.code)
    return error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    get_logger().warning(
        "request_validation_failed",
        error_code="VALIDATION_ERROR",
        validation_error_count=len(exc.errors()),
    )
    return error_response(
        request,
        status_code=422,
        code="VALIDATION_ERROR",
        message="The request is invalid.",
    )


async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    get_logger().warning(
        "http_error",
        error_code="HTTP_ERROR",
        status_code=exc.status_code,
    )
    message = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
    return error_response(
        request,
        status_code=exc.status_code,
        code="HTTP_ERROR",
        message=message,
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Record a stable error event without serializing potentially sensitive exception text.
    get_logger().error(
        "unexpected_error",
        error_code="INTERNAL_SERVER_ERROR",
        request_id=get_request_id(request),
    )
    return error_response(
        request,
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred.",
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register all exception handlers in one place."""

    app.add_exception_handler(ApplicationError, application_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unexpected_error_handler)
