"""Publishing queue, scheduling, atomic lifecycle, and worker tests."""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.assets.models import Asset
from apps.api.errors.exceptions import ApplicationError
from apps.api.publishing.models import Publication, PublicationStatus
from apps.api.publishing.providers import PublishingProviderError, PublishingProviderResolver
from apps.api.publishing.queue import PUBLISHING_TASK_NAME, PublishingQueueService
from apps.api.publishing.repository import PublicationRepository
from apps.api.publishing.schemas import PublicationSchedule, PublicationUpdate
from apps.api.publishing.service import PublishingService
from apps.api.repositories import AssetRepository
from apps.worker.tasks import _run_publication, execute_publication

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


def make_publication(status: PublicationStatus = PublicationStatus.PENDING) -> Publication:
    return Publication(
        id=uuid4(),
        asset_id=uuid4(),
        provider="mock",
        status=status,
        title="Scheduled video",
        description=None,
        provider_metadata={},
        created_at=NOW,
        updated_at=NOW,
    )


def recording_sender(calls: list[dict[str, object]]):
    def send(task_name: str, **kwargs: object) -> Mock:
        calls.append({"task_name": task_name, **kwargs})
        result = Mock()
        result.id = str(kwargs["task_id"])
        return result

    return send


def transition_side_effect(publication: Publication):
    async def transition(
        publication_id,
        from_status,
        to_status,
        update_in,
    ):
        if publication.id != publication_id or publication.status is not from_status:
            return None
        publication.status = to_status
        for field, value in update_in.model_dump(exclude_unset=True).items():
            setattr(publication, field, value)
        return publication

    return transition


def test_schedule_schema_requires_timezone_and_normalizes_utc() -> None:
    schedule = PublicationSchedule(
        scheduled_at=datetime(2026, 8, 14, 12, 0, tzinfo=timezone(timedelta(hours=9)))
    )

    assert schedule.scheduled_at == datetime(2026, 8, 14, 3, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="timezone offset"):
        PublicationSchedule(scheduled_at=datetime(2026, 8, 14, 12, 0))


@pytest.mark.asyncio
async def test_queue_service_immediate_and_scheduled_enqueue() -> None:
    for scheduled_at in (None, NOW + timedelta(hours=2)):
        publication = make_publication()
        repository = AsyncMock(spec=PublicationRepository)
        repository.get_by_id.return_value = publication
        repository.transition_status.side_effect = transition_side_effect(publication)
        calls: list[dict[str, object]] = []

        service = PublishingQueueService(
            repository,
            task_sender=recording_sender(calls),
            clock=lambda: NOW,
        )
        queued = await service.enqueue(publication.id, scheduled_at=scheduled_at)

        assert queued.status is PublicationStatus.QUEUED
        assert queued.queued_at == NOW
        assert queued.scheduled_at == scheduled_at
        assert queued.task_id is not None
        assert calls[0]["task_name"] == PUBLISHING_TASK_NAME
        assert calls[0]["args"] == [str(publication.id)]
        assert set(calls[0]) == {"task_name", "args", "queue", "task_id", "eta"}


@pytest.mark.asyncio
async def test_queue_service_rejects_past_and_duplicate_enqueue() -> None:
    publication = make_publication()
    repository = AsyncMock(spec=PublicationRepository)
    repository.get_by_id.return_value = publication
    sender = Mock()
    service = PublishingQueueService(repository, task_sender=sender, clock=lambda: NOW)

    with pytest.raises(ApplicationError) as past:
        await service.enqueue(publication.id, scheduled_at=NOW - timedelta(seconds=1))
    assert past.value.code == "SCHEDULE_IN_PAST"

    publication.status = PublicationStatus.QUEUED
    with pytest.raises(ApplicationError) as duplicate:
        await service.enqueue(publication.id)
    assert duplicate.value.code == "INVALID_PUBLICATION_STATE"
    sender.assert_not_called()


@pytest.mark.asyncio
async def test_queue_failure_is_safe_and_terminal() -> None:
    publication = make_publication()
    repository = AsyncMock(spec=PublicationRepository)
    repository.get_by_id.return_value = publication
    repository.transition_status.side_effect = transition_side_effect(publication)
    sender = Mock(side_effect=RuntimeError("redis://user:secret@example.invalid"))
    service = PublishingQueueService(repository, task_sender=sender, clock=lambda: NOW)

    with pytest.raises(ApplicationError) as raised:
        await service.enqueue(publication.id)

    assert raised.value.code == "PUBLISHING_QUEUE_ERROR"
    assert publication.status is PublicationStatus.FAILED
    assert publication.error_message == "The publication could not be queued."
    assert "secret" not in publication.error_message


@pytest.mark.asyncio
async def test_repository_atomic_transition_commits_and_refreshes() -> None:
    session = AsyncMock(spec=AsyncSession)
    publication = make_publication(PublicationStatus.QUEUED)
    result = Mock()
    result.scalar_one_or_none.return_value = publication
    session.execute.return_value = result
    repository = PublicationRepository(session)

    transitioned = await repository.transition_status(
        publication.id,
        PublicationStatus.QUEUED,
        PublicationStatus.PUBLISHING,
        PublicationUpdate(started_at=NOW),
    )

    assert transitioned is publication
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(publication)


@pytest.mark.asyncio
async def test_worker_publish_is_idempotent_and_uses_service_boundary() -> None:
    publication = make_publication(PublicationStatus.QUEUED)
    asset = Asset(
        id=publication.asset_id,
        object_key="assets/final.mp4",
        filename="final.mp4",
        content_type="video/mp4",
        size_bytes=10,
        created_at=NOW,
    )
    repository = AsyncMock(spec=PublicationRepository)
    repository.get_by_id.return_value = publication
    repository.transition_status.side_effect = transition_side_effect(publication)
    assets = AsyncMock(spec=AssetRepository)
    assets.get_by_id.return_value = asset
    provider = AsyncMock()
    provider.publish.return_value.external_id = "video-1"
    provider.publish.return_value.external_url = "https://example.invalid/video-1"
    provider.publish.return_value.metadata = {"provider": "mock"}
    resolver = PublishingProviderResolver({"mock": provider})
    service = PublishingService(repository, assets, resolver)

    first = await _run_publication(service, publication.id)
    second = await _run_publication(service, publication.id)

    assert first["status"] == "published"
    assert second["status"] == "published"
    provider.publish.assert_awaited_once()
    assert publication.status is PublicationStatus.PUBLISHED


@pytest.mark.asyncio
async def test_worker_safe_failure_contract_and_task_registration(caplog) -> None:
    publication_id = uuid4()
    service = AsyncMock(spec=PublishingService)
    service.publish_queued.side_effect = RuntimeError("refresh-token-secret")

    result = await _run_publication(service, publication_id)

    assert execute_publication.name == "apps.worker.tasks.execute_publication"
    assert result == {"status": "failed", "error": "PUBLISHING_WORKER_ERROR"}
    service.fail_queued_or_publishing.assert_awaited_once_with(publication_id)
    assert "refresh-token-secret" not in caplog.text


@pytest.mark.asyncio
async def test_queued_provider_failure_persists_failed_and_is_not_retried() -> None:
    publication = make_publication(PublicationStatus.QUEUED)
    asset = Asset(
        id=publication.asset_id,
        object_key="assets/final.mp4",
        filename="final.mp4",
        content_type="video/mp4",
        size_bytes=10,
        created_at=NOW,
    )
    repository = AsyncMock(spec=PublicationRepository)
    repository.get_by_id.return_value = publication
    repository.transition_status.side_effect = transition_side_effect(publication)
    assets = AsyncMock(spec=AssetRepository)
    assets.get_by_id.return_value = asset
    provider = AsyncMock()
    provider.publish.side_effect = PublishingProviderError(
        "MOCK_PROVIDER_FAILURE",
        "The mock provider could not publish the asset.",
    )
    service = PublishingService(
        repository,
        assets,
        PublishingProviderResolver({"mock": provider}),
    )

    first = await _run_publication(service, publication.id)
    second = await _run_publication(service, publication.id)

    assert first == {"status": "failed", "error": "MOCK_PROVIDER_FAILURE"}
    assert second["status"] == "failed"
    assert publication.status is PublicationStatus.FAILED
    assert publication.error_code == "MOCK_PROVIDER_FAILURE"
    provider.publish.assert_awaited_once()
