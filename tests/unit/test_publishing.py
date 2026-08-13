"""Unit tests for the publishing domain, providers, repository, and service."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.assets.models import Asset
from apps.api.errors.exceptions import ApplicationError
from apps.api.publishing.models import Publication, PublicationStatus
from apps.api.publishing.providers import (
    MockPublishingProvider,
    PublishingProvider,
    PublishingProviderResolver,
    PublishingResponse,
)
from apps.api.publishing.repository import PublicationRepository
from apps.api.publishing.schemas import PublicationCreate
from apps.api.publishing.service import PublishingService
from apps.api.publishing.youtube import YouTubeUploadError
from apps.api.repositories import AssetRepository


def make_video_asset() -> Asset:
    asset_id = uuid4()
    return Asset(
        id=asset_id,
        object_key=f"assets/{asset_id}/final.mp4",
        filename="final.mp4",
        content_type="video/mp4",
        size_bytes=1024,
        created_at=datetime.now(UTC),
    )


def make_publication(asset: Asset) -> Publication:
    now = datetime.now(UTC)
    return Publication(
        id=uuid4(),
        asset_id=asset.id,
        provider="mock",
        status=PublicationStatus.PENDING,
        title="Launch video",
        description="AI Video OS Runtime MVP",
        provider_metadata={},
        created_at=now,
        updated_at=now,
    )


def test_publication_domain_and_response_contract() -> None:
    asset = make_video_asset()
    publication = make_publication(asset)
    response = PublishingResponse(
        external_id="external-1",
        external_url="https://example.invalid/external-1",
        metadata={"provider": "mock"},
    )

    assert publication.status is PublicationStatus.PENDING
    assert [status.value for status in PublicationStatus] == [
        "pending",
        "publishing",
        "published",
        "failed",
    ]
    assert response.external_id == "external-1"
    assert response.metadata == {"provider": "mock"}


@pytest.mark.asyncio
async def test_mock_provider_and_resolution() -> None:
    asset = make_video_asset()
    provider = PublishingProviderResolver().resolve("MOCK")

    response = await provider.publish(asset, title="Title", description=None)

    assert isinstance(provider, MockPublishingProvider)
    assert response.external_id == f"mock-{asset.id}"
    assert response.external_url.endswith(str(asset.id))
    with pytest.raises(ValueError, match="Unsupported publishing provider"):
        PublishingProviderResolver().resolve("youtube")


@pytest.mark.asyncio
async def test_publication_repository_create_and_list_by_asset() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.add = Mock()
    repository = PublicationRepository(session)
    asset = make_video_asset()
    publication_in = PublicationCreate(
        asset_id=asset.id,
        provider="mock",
        title="Title",
    )

    def refresh(instance: Publication) -> None:
        instance.id = uuid4()
        instance.status = PublicationStatus.PENDING

    session.refresh.side_effect = refresh
    created = await repository.create(publication_in)
    result = Mock()
    result.scalars.return_value.all.return_value = [created]
    session.execute.return_value = result

    publications = await repository.list_by_asset(asset.id)

    assert created.status is PublicationStatus.PENDING
    assert publications == [created]
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


def make_service(
    asset: Asset | None,
) -> tuple[PublishingService, AsyncMock, AsyncMock, PublishingProviderResolver]:
    publication_repo = AsyncMock(spec=PublicationRepository)
    asset_repo = AsyncMock(spec=AssetRepository)
    asset_repo.get_by_id.return_value = asset
    resolver = PublishingProviderResolver()
    return (
        PublishingService(publication_repo, asset_repo, resolver),
        publication_repo,
        asset_repo,
        resolver,
    )


@pytest.mark.asyncio
async def test_service_creates_and_lists_publications_for_video_asset() -> None:
    asset = make_video_asset()
    service, publication_repo, _, _ = make_service(asset)
    publication_in = PublicationCreate(asset_id=asset.id, provider="mock", title="Title")
    publication = make_publication(asset)
    publication_repo.create.return_value = publication
    publication_repo.list_by_asset.return_value = [publication]

    created = await service.create(publication_in)
    listed = await service.list_by_asset(asset.id)

    assert created is publication
    assert listed == [publication]
    publication_repo.create.assert_awaited_once_with(publication_in)


@pytest.mark.asyncio
async def test_service_rejects_missing_non_video_and_unsupported_provider() -> None:
    missing_service, _, _, _ = make_service(None)
    missing = PublicationCreate(asset_id=uuid4(), provider="mock", title="Title")
    with pytest.raises(ApplicationError) as missing_error:
        await missing_service.create(missing)
    assert missing_error.value.code == "ASSET_NOT_FOUND"

    image = make_video_asset()
    image.content_type = "image/png"
    image_service, _, _, _ = make_service(image)
    with pytest.raises(ApplicationError) as image_error:
        await image_service.create(
            PublicationCreate(asset_id=image.id, provider="mock", title="Title")
        )
    assert image_error.value.code == "ASSET_NOT_PUBLISHABLE"

    video = make_video_asset()
    provider_service, _, _, _ = make_service(video)
    with pytest.raises(ApplicationError) as provider_error:
        await provider_service.create(
            PublicationCreate(asset_id=video.id, provider="youtube", title="Title")
        )
    assert provider_error.value.code == "UNSUPPORTED_PUBLISHING_PROVIDER"


@pytest.mark.asyncio
async def test_service_publishes_and_persists_provider_result() -> None:
    asset = make_video_asset()
    publication = make_publication(asset)
    service, publication_repo, _, _ = make_service(asset)
    publication_repo.get_by_id.return_value = publication

    async def update(publication_id, schema):
        assert publication_id == publication.id
        for field, value in schema.model_dump(exclude_unset=True).items():
            setattr(publication, field, value)
        return publication

    publication_repo.update.side_effect = update

    published = await service.publish(publication.id)

    assert published.status is PublicationStatus.PUBLISHED
    assert published.external_id == f"mock-{asset.id}"
    assert published.external_url is not None
    assert published.provider_metadata["provider"] == "mock"
    assert published.published_at is not None
    assert publication_repo.update.await_count == 2


class FailingProvider(PublishingProvider):
    async def publish(
        self,
        asset: Asset,
        *,
        title: str,
        description: str | None,
    ) -> PublishingResponse:
        raise RuntimeError("secret provider detail")


@pytest.mark.asyncio
async def test_service_failure_persists_safe_error() -> None:
    asset = make_video_asset()
    publication = make_publication(asset)
    service, publication_repo, _, resolver = make_service(asset)
    publication_repo.get_by_id.return_value = publication
    resolver.resolve = Mock(return_value=FailingProvider())

    async def update(publication_id, schema):
        for field, value in schema.model_dump(exclude_unset=True).items():
            setattr(publication, field, value)
        return publication

    publication_repo.update.side_effect = update

    with pytest.raises(ApplicationError) as raised:
        await service.publish(publication.id)

    assert raised.value.code == "PUBLISHING_PROVIDER_ERROR"
    assert publication.status is PublicationStatus.FAILED
    assert publication.error_code == "PUBLISHING_PROVIDER_ERROR"
    assert publication.error_message == "The publishing provider could not publish the asset."
    assert "secret" not in publication.error_message


@pytest.mark.asyncio
async def test_service_requires_pending_publication() -> None:
    asset = make_video_asset()
    publication = make_publication(asset)
    publication.status = PublicationStatus.PUBLISHED
    service, publication_repo, _, _ = make_service(asset)
    publication_repo.get_by_id.return_value = publication

    with pytest.raises(ApplicationError) as raised:
        await service.publish(publication.id)

    assert raised.value.code == "INVALID_PUBLICATION_STATE"


@pytest.mark.asyncio
async def test_service_persists_specific_safe_youtube_error() -> None:
    asset = make_video_asset()
    publication = make_publication(asset)
    publication.provider = "youtube"
    service, publication_repo, _, resolver = make_service(asset)
    publication_repo.get_by_id.return_value = publication
    provider = AsyncMock(spec=PublishingProvider)
    provider.publish.side_effect = YouTubeUploadError()
    resolver.resolve = Mock(return_value=provider)

    async def update(publication_id, schema):
        for field, value in schema.model_dump(exclude_unset=True).items():
            setattr(publication, field, value)
        return publication

    publication_repo.update.side_effect = update

    with pytest.raises(ApplicationError) as raised:
        await service.publish(publication.id)

    assert raised.value.code == "YOUTUBE_UPLOAD_ERROR"
    assert publication.status is PublicationStatus.FAILED
    assert publication.error_code == "YOUTUBE_UPLOAD_ERROR"
    assert publication.error_message == "YouTube could not upload the video."
