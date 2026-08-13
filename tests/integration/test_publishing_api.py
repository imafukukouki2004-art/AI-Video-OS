"""API integration tests for the publishing foundation."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import get_publishing_service
from apps.api.errors import register_error_handlers
from apps.api.errors.exceptions import ApplicationError
from apps.api.publishing.models import Publication, PublicationStatus
from apps.api.publishing.router import router
from apps.api.publishing.service import PublishingService


def make_publication() -> Publication:
    now = datetime.now(UTC)
    return Publication(
        id=uuid4(),
        asset_id=uuid4(),
        provider="mock",
        status=PublicationStatus.PENDING,
        title="Runtime MVP",
        description="Final video",
        provider_metadata={},
        created_at=now,
        updated_at=now,
    )


def make_client(service: PublishingService) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_publishing_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def test_create_get_list_and_publish_publication_api() -> None:
    publication = make_publication()
    published = make_publication()
    published.id = publication.id
    published.asset_id = publication.asset_id
    published.status = PublicationStatus.PUBLISHED
    published.external_id = "mock-external"
    published.external_url = "https://example.invalid/mock-external"
    published.provider_metadata = {"provider": "mock"}
    published.published_at = datetime.now(UTC)
    service = AsyncMock(spec=PublishingService)
    service.create.return_value = publication
    service.get_by_id.return_value = publication
    service.list_by_asset.return_value = [publication]
    service.publish.return_value = published

    with make_client(service) as client:
        created = client.post(
            "/publications",
            json={
                "asset_id": str(publication.asset_id),
                "provider": "mock",
                "title": "Runtime MVP",
                "description": "Final video",
            },
        )
        fetched = client.get(f"/publications/{publication.id}")
        listed = client.get(f"/assets/{publication.asset_id}/publications")
        publish = client.post(f"/publications/{publication.id}/publish")

    assert created.status_code == 201
    assert fetched.status_code == 200
    assert listed.status_code == 200
    assert listed.json()[0]["asset_id"] == str(publication.asset_id)
    assert publish.status_code == 200
    assert publish.json()["status"] == "published"
    assert publish.json()["external_id"] == "mock-external"
    assert "credentials" not in publish.json()


def test_missing_publication_uses_safe_error_contract() -> None:
    service = AsyncMock(spec=PublishingService)
    service.get_by_id.return_value = None

    with make_client(service) as client:
        response = client.get(f"/publications/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PUBLICATION_NOT_FOUND"


def test_create_rejects_invalid_asset_and_unsupported_provider() -> None:
    service = AsyncMock(spec=PublishingService)
    service.create.side_effect = ApplicationError(
        code="ASSET_NOT_PUBLISHABLE",
        message="The asset is not a publishable video.",
        status_code=422,
    )
    asset_id = uuid4()

    with make_client(service) as client:
        invalid_asset = client.post(
            "/publications",
            json={"asset_id": str(asset_id), "provider": "mock", "title": "Image"},
        )
        service.create.side_effect = ApplicationError(
            code="UNSUPPORTED_PUBLISHING_PROVIDER",
            message="The publishing provider is not supported.",
            status_code=422,
        )
        unsupported = client.post(
            "/publications",
            json={"asset_id": str(asset_id), "provider": "youtube", "title": "Video"},
        )

    assert invalid_asset.status_code == 422
    assert invalid_asset.json()["error"]["code"] == "ASSET_NOT_PUBLISHABLE"
    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "UNSUPPORTED_PUBLISHING_PROVIDER"
