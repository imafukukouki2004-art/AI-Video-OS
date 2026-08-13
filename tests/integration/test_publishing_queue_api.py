"""API integration tests for publication enqueue and scheduling."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import get_publishing_queue_service
from apps.api.errors import register_error_handlers
from apps.api.errors.exceptions import ApplicationError
from apps.api.publishing.models import Publication, PublicationStatus
from apps.api.publishing.queue import PublishingQueueService
from apps.api.publishing.router import router


def make_queued_publication() -> Publication:
    now = datetime.now(UTC)
    return Publication(
        id=uuid4(),
        asset_id=uuid4(),
        provider="mock",
        status=PublicationStatus.QUEUED,
        title="Queued video",
        description=None,
        provider_metadata={},
        queued_at=now,
        task_id="task-queue-1",
        created_at=now,
        updated_at=now,
    )


def make_client(queue_service: PublishingQueueService) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_publishing_queue_service] = lambda: queue_service
    return TestClient(app, raise_server_exceptions=False)


def test_immediate_and_scheduled_enqueue_api() -> None:
    queued = make_queued_publication()
    scheduled = make_queued_publication()
    scheduled.scheduled_at = datetime.now(UTC) + timedelta(hours=1)
    service = AsyncMock(spec=PublishingQueueService)
    service.enqueue.side_effect = [queued, scheduled]

    with make_client(service) as client:
        immediate = client.post(f"/publications/{queued.id}/enqueue")
        future = datetime.now(UTC) + timedelta(hours=1)
        schedule = client.post(
            f"/publications/{scheduled.id}/schedule",
            json={"scheduled_at": future.isoformat()},
        )

    assert immediate.status_code == 202
    assert immediate.json()["status"] == "queued"
    assert immediate.json()["task_id"] == "task-queue-1"
    assert schedule.status_code == 202
    assert schedule.json()["scheduled_at"] is not None


def test_schedule_rejects_naive_time_and_duplicate_queue() -> None:
    queued = make_queued_publication()
    service = AsyncMock(spec=PublishingQueueService)
    service.enqueue.side_effect = ApplicationError(
        code="INVALID_PUBLICATION_STATE",
        message="Only pending publications can be queued.",
        status_code=409,
    )

    with make_client(service) as client:
        naive = client.post(
            f"/publications/{queued.id}/schedule",
            json={"scheduled_at": "2026-08-14T12:00:00"},
        )
        duplicate = client.post(f"/publications/{queued.id}/enqueue")

    assert naive.status_code == 422
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "INVALID_PUBLICATION_STATE"


def test_schedule_rejects_past_time_with_safe_error() -> None:
    queued = make_queued_publication()
    service = AsyncMock(spec=PublishingQueueService)
    service.enqueue.side_effect = ApplicationError(
        code="SCHEDULE_IN_PAST",
        message="scheduled_at must be in the future.",
        status_code=422,
    )

    with make_client(service) as client:
        response = client.post(
            f"/publications/{queued.id}/schedule",
            json={"scheduled_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat()},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SCHEDULE_IN_PAST"
