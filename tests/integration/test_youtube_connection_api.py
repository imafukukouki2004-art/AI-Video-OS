"""API integration tests for YouTube OAuth connection routes."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import get_youtube_connection_service
from apps.api.errors import register_error_handlers
from apps.api.errors.exceptions import ApplicationError
from apps.api.publishing.connection_service import YouTubeConnectionService
from apps.api.publishing.models import PublishingConnection, PublishingConnectionStatus
from apps.api.publishing.router import router
from apps.api.publishing.schemas import YouTubeAuthorizationResponse
from apps.api.publishing.youtube import YOUTUBE_UPLOAD_SCOPE


def connection(status: PublishingConnectionStatus):
    now = datetime.now(UTC)
    return PublishingConnection(
        id=uuid4(),
        provider="youtube",
        status=status,
        scopes=[YOUTUBE_UPLOAD_SCOPE],
        created_at=now,
        updated_at=now,
        connected_at=now if status is PublishingConnectionStatus.CONNECTED else None,
        disconnected_at=(now if status is PublishingConnectionStatus.DISCONNECTED else None),
    )


def client(service: YouTubeConnectionService) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_youtube_connection_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def test_oauth_start_callback_get_and_disconnect_expose_no_secrets() -> None:
    service = AsyncMock(spec=YouTubeConnectionService)
    connected = connection(PublishingConnectionStatus.CONNECTED)
    disconnected = connection(PublishingConnectionStatus.DISCONNECTED)
    service.authorize.return_value = YouTubeAuthorizationResponse(
        connection_id=connected.id,
        authorization_url="https://accounts.google.com/o/oauth2/v2/auth?state=fixture",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    service.callback.return_value = connected
    service.get.return_value = connected
    service.disconnect.return_value = disconnected

    with client(service) as api:
        start = api.post("/publishing/connections/youtube/authorize")
        callback = api.get(
            "/publishing/connections/youtube/callback",
            params={"state": "fixture", "code": "sensitive-code"},
        )
        fetched = api.get(f"/publishing/connections/{connected.id}")
        removed = api.delete(f"/publishing/connections/{connected.id}")

    assert start.status_code == 201
    assert callback.status_code == 200
    assert fetched.status_code == 200
    assert removed.json()["status"] == "disconnected"
    for response in (start, callback, fetched, removed):
        serialized = response.text.lower()
        assert "refresh_token" not in serialized
        assert "access_token" not in serialized
        assert "encrypted_refresh_token" not in serialized
        assert "client_secret" not in serialized
        assert "sensitive-code" not in serialized


def test_callback_safe_error_contract() -> None:
    service = AsyncMock(spec=YouTubeConnectionService)
    service.callback.side_effect = ApplicationError(
        code="YOUTUBE_OAUTH_INVALID_STATE",
        message="OAuth state is invalid.",
        status_code=400,
    )

    with client(service) as api:
        response = api.get(
            "/publishing/connections/youtube/callback",
            params={"state": "wrong", "code": "sensitive-code"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "YOUTUBE_OAUTH_INVALID_STATE"
    assert "sensitive-code" not in response.text
