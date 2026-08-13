"""Mock-provider E2E contract for queue to publishing completion."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from apps.api.assets.models import Asset
from apps.api.publishing.models import Publication, PublicationStatus
from apps.api.publishing.providers import (
    PublishingProvider,
    PublishingProviderResolver,
    PublishingResponse,
)
from apps.api.publishing.queue import PublishingQueueService
from apps.api.publishing.repository import PublicationRepository
from apps.api.publishing.service import PublishingService
from apps.api.repositories import AssetRepository
from apps.worker.tasks import _run_publication


class CountingProvider(PublishingProvider):
    def __init__(self) -> None:
        self.calls = 0

    async def publish(
        self,
        asset: Asset,
        *,
        title: str,
        description: str | None,
    ) -> PublishingResponse:
        self.calls += 1
        return PublishingResponse(
            external_id="queued-video-1",
            external_url="https://example.invalid/queued-video-1",
            metadata={"provider": "mock"},
        )


@pytest.mark.asyncio
async def test_publication_enqueue_worker_service_provider_e2e() -> None:
    now = datetime.now(UTC)
    asset = Asset(
        id=uuid4(),
        object_key="assets/runtime/final.mp4",
        filename="final.mp4",
        content_type="video/mp4",
        size_bytes=5,
        created_at=now,
    )
    publication = Publication(
        id=uuid4(),
        asset_id=asset.id,
        provider="mock",
        status=PublicationStatus.PENDING,
        title="Runtime MVP",
        description="Queued publication",
        provider_metadata={},
        created_at=now,
        updated_at=now,
    )
    repository = AsyncMock(spec=PublicationRepository)
    repository.get_by_id.return_value = publication

    async def transition(publication_id, from_status, to_status, update_in):
        if publication.id != publication_id or publication.status is not from_status:
            return None
        publication.status = to_status
        for field, value in update_in.model_dump(exclude_unset=True).items():
            setattr(publication, field, value)
        return publication

    repository.transition_status.side_effect = transition
    task = Mock()

    def send_task(task_name, **kwargs):
        task.id = kwargs["task_id"]
        return task

    queue = PublishingQueueService(repository, task_sender=send_task)
    queued = await queue.enqueue(publication.id)

    assets = AsyncMock(spec=AssetRepository)
    assets.get_by_id.return_value = asset
    provider = CountingProvider()
    publishing = PublishingService(
        repository,
        assets,
        PublishingProviderResolver({"mock": provider}),
    )
    result = await _run_publication(publishing, publication.id)
    duplicate = await _run_publication(publishing, publication.id)

    assert queued.status in {PublicationStatus.QUEUED, PublicationStatus.PUBLISHED}
    assert result == {"status": "published", "publication_id": str(publication.id)}
    assert duplicate == result
    assert publication.status is PublicationStatus.PUBLISHED
    assert publication.external_id == "queued-video-1"
    assert publication.task_id == task.id
    assert provider.calls == 1
