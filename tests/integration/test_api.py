"""FastAPI integration tests."""

from typing import NoReturn

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.application import create_app
from apps.api.config import Settings


def make_app() -> FastAPI:
    return create_app(Settings(app_env="test", log_level="CRITICAL", _env_file=None))


def test_application_factory_and_import() -> None:
    from apps.api.main import app

    assert isinstance(app, FastAPI)
    assert isinstance(make_app(), FastAPI)


def test_health_response_schema() -> None:
    with TestClient(make_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ai-video-os-api",
        "environment": "test",
    }
    assert response.headers["X-Request-ID"]


def test_ready_response_schema() -> None:
    with TestClient(make_app()) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "ai-video-os-api",
        "environment": "test",
    }


def test_safe_request_id_is_preserved() -> None:
    with TestClient(make_app()) as client:
        response = client.get("/health", headers={"X-Request-ID": "client-request-123"})

    assert response.headers["X-Request-ID"] == "client-request-123"


def test_unsafe_request_id_is_replaced() -> None:
    with TestClient(make_app()) as client:
        response = client.get("/health", headers={"X-Request-ID": "unsafe request id"})

    assert response.headers["X-Request-ID"] != "unsafe request id"


def test_validation_error_uses_common_contract() -> None:
    app = make_app()

    @app.get("/_test/validation")
    async def validation_route(value: int) -> dict[str, int]:
        return {"value": value}

    with TestClient(app) as client:
        response = client.get("/_test/validation", params={"value": "not-an-int"})

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["message"] == "The request is invalid."
    assert payload["error"]["request_id"] == response.headers["X-Request-ID"]


def test_unexpected_error_does_not_expose_internal_details() -> None:
    app = make_app()

    @app.get("/_test/error", response_model=None)
    async def error_route() -> NoReturn:
        raise RuntimeError("sensitive implementation detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/_test/error")

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "INTERNAL_SERVER_ERROR",
        "message": "An unexpected error occurred.",
        "request_id": response.headers["X-Request-ID"],
    }
    assert "sensitive implementation detail" not in response.text


def test_openapi_document_is_available() -> None:
    with TestClient(make_app()) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]
    assert "/ready" in response.json()["paths"]
