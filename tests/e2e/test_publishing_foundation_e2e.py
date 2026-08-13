"""End-to-end domain test for publishing an existing Runtime MVP video Asset."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from apps.api.assets.models import Asset
from apps.api.publishing.models import Publication, PublicationStatus
from apps.api.publishing.providers import PublishingProviderResolver
from apps.api.publishing.repository import PublicationRepository
from apps.api.publishing.schemas import PublicationCreate
from apps.api.publishing.service import PublishingService
from apps.api.repositories import AssetRepository


@pytest.mark.asyncio
async def test_existing_video_asset_is_published_through_mock_provider() -> None:
    now = datetime.now(UTC)
    asset = Asset(
        id=uuid4(),
        object_key="assets/runtime/final-video.mp4",
        filename="final-video.mp4",
        content_type="video/mp4",
        size_bytes=2048,
        created_at=now,
    )
    publication_repository = AsyncMock(spec=PublicationRepository)
    asset_repository = AsyncMock(spec=AssetRepository)
    asset_repository.get_by_id.return_value = asset
    service = PublishingService(
        publication_repository,
        asset_repository,
        PublishingProviderResolver(),
    )
    publication = Publication(
        id=uuid4(),
        asset_id=asset.id,
        provider="mock",
        status=PublicationStatus.PENDING,
        title="Runtime MVP final video",
        description="Publish the existing generated video.",
        provider_metadata={},
        created_at=now,
        updated_at=now,
    )
    publication_repository.create.return_value = publication
    publication_repository.get_by_id.return_value = publication

    async def persist_update(publication_id, update):
        assert publication_id == publication.id
        for field, value in update.model_dump(exclude_unset=True).items():
            setattr(publication, field, value)
        return publication

    publication_repository.update.side_effect = persist_update

    created = await service.create(
        PublicationCreate(
            asset_id=asset.id,
            provider="mock",
            title=publication.title,
            description=publication.description,
        )
    )
    published = await service.publish(created.id)

    assert created.asset_id == asset.id
    assert published.status is PublicationStatus.PUBLISHED
    assert published.external_id == f"mock-{asset.id}"
    assert published.external_url == f"https://example.invalid/publications/{asset.id}"
    assert published.provider_metadata == {
        "provider": "mock",
        "title": "Runtime MVP final video",
    }
    assert published.published_at is not None
    assert publication_repository.update.await_count == 2
