"""External-call-free E2E test for YouTube publication persistence."""

from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import SecretStr

from apps.api.assets.models import Asset
from apps.api.publishing.models import Publication, PublicationStatus
from apps.api.publishing.providers import PublishingProviderResolver
from apps.api.publishing.repository import PublicationRepository
from apps.api.publishing.schemas import PublicationCreate
from apps.api.publishing.service import PublishingService
from apps.api.publishing.youtube import YouTubeCredentialSettings, YouTubePublishingProvider
from apps.api.repositories import AssetRepository
from apps.api.storage import ObjectStorage, StoredObject


@pytest.mark.asyncio
async def test_existing_video_asset_is_published_to_youtube_with_mock_sdk() -> None:
    now = datetime.now(UTC)
    asset = Asset(
        id=uuid4(),
        object_key="assets/runtime/final-video.mp4",
        filename="final-video.mp4",
        content_type="video/mp4",
        size_bytes=5,
        created_at=now,
    )
    storage = AsyncMock(spec=ObjectStorage)
    storage.download.return_value = StoredObject(body=b"video", content_type="video/mp4")
    insert_request = Mock()
    insert_request.execute.return_value = {"id": "youtube-video-id"}
    videos = Mock()
    videos.insert.return_value = insert_request
    client = Mock()
    client.videos.return_value = videos
    media_factory = Mock(return_value="mock-media")
    youtube = YouTubePublishingProvider(
        storage,
        YouTubeCredentialSettings(
            client_id=SecretStr("fixture"),
            client_secret=SecretStr("fixture"),
            refresh_token=SecretStr("fixture"),
        ),
        client_factory=lambda: client,
        media_upload_factory=media_factory,
    )
    publication_repository = AsyncMock(spec=PublicationRepository)
    asset_repository = AsyncMock(spec=AssetRepository)
    asset_repository.get_by_id.return_value = asset
    publication = Publication(
        id=uuid4(),
        asset_id=asset.id,
        provider="youtube",
        status=PublicationStatus.PENDING,
        title="Runtime MVP final video",
        description="Private YouTube upload",
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
    service = PublishingService(
        publication_repository,
        asset_repository,
        PublishingProviderResolver({"youtube": youtube}),
    )

    created = await service.create(
        PublicationCreate(
            asset_id=asset.id,
            provider="youtube",
            title=publication.title,
            description=publication.description,
        )
    )
    published = await service.publish(created.id)

    assert published.status is PublicationStatus.PUBLISHED
    assert published.external_id == "youtube-video-id"
    assert published.external_url == "https://www.youtube.com/watch?v=youtube-video-id"
    assert published.provider_metadata == {
        "provider": "youtube",
        "privacy_status": "private",
    }
    storage.download.assert_awaited_once_with(asset.object_key)
    videos.insert.assert_called_once()
    media_stream = media_factory.call_args.args[0]
    assert isinstance(media_stream, BytesIO)
    assert media_stream.closed
    assert publication_repository.update.await_count == 2
