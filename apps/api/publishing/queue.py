"""Celery-backed queue service for immediate and scheduled publication."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol, cast
from uuid import UUID, uuid4

from apps.api.errors.exceptions import ApplicationError
from apps.api.publishing.models import Publication, PublicationStatus
from apps.api.publishing.repository import PublicationRepository
from apps.api.publishing.schemas import PublicationUpdate
from apps.worker.celery_app import celery_app

PUBLISHING_TASK_NAME = "apps.worker.tasks.execute_publication"
PUBLISHING_QUEUE_NAME = "ai-video-os"


class TaskResult(Protocol):
    id: str


class TaskSender(Protocol):
    def __call__(
        self,
        task_name: str,
        *,
        args: list[str],
        queue: str,
        task_id: str,
        eta: datetime | None,
    ) -> TaskResult: ...


def send_publication_task(
    task_name: str,
    *,
    args: list[str],
    queue: str,
    task_id: str,
    eta: datetime | None,
) -> TaskResult:
    return cast(
        TaskResult,
        celery_app.send_task(
            task_name,
            args=args,
            queue=queue,
            task_id=task_id,
            eta=eta,
        ),
    )


class PublishingQueueService:
    """Claim publications for queueing and dispatch ID-only Celery tasks."""

    def __init__(
        self,
        publication_repository: PublicationRepository,
        *,
        task_sender: TaskSender = send_publication_task,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.publication_repository = publication_repository
        self._task_sender = task_sender
        self._clock = clock or (lambda: datetime.now(UTC))

    async def enqueue(
        self,
        publication_id: UUID,
        *,
        scheduled_at: datetime | None = None,
    ) -> Publication:
        now = self._clock().astimezone(UTC)
        normalized_schedule = self._validate_schedule(scheduled_at, now)
        publication = await self.publication_repository.get_by_id(publication_id)
        if publication is None:
            raise ApplicationError(
                code="PUBLICATION_NOT_FOUND",
                message="Publication not found.",
                status_code=404,
            )
        if publication.status is not PublicationStatus.PENDING:
            raise self._invalid_state()

        task_id = str(uuid4())
        queued = await self.publication_repository.transition_status(
            publication_id,
            PublicationStatus.PENDING,
            PublicationStatus.QUEUED,
            PublicationUpdate(
                scheduled_at=normalized_schedule,
                queued_at=now,
                task_id=task_id,
                error_code=None,
                error_message=None,
            ),
        )
        if queued is None:
            raise self._invalid_state()

        try:
            task = self._task_sender(
                PUBLISHING_TASK_NAME,
                args=[str(publication_id)],
                queue=PUBLISHING_QUEUE_NAME,
                task_id=task_id,
                eta=normalized_schedule,
            )
        except Exception as error:
            await self.publication_repository.transition_status(
                publication_id,
                PublicationStatus.QUEUED,
                PublicationStatus.FAILED,
                PublicationUpdate(
                    error_code="PUBLISHING_QUEUE_ERROR",
                    error_message="The publication could not be queued.",
                ),
            )
            raise ApplicationError(
                code="PUBLISHING_QUEUE_ERROR",
                message="The publication could not be queued.",
                status_code=503,
            ) from error

        if str(task.id) != task_id:
            await self.publication_repository.transition_status(
                publication_id,
                PublicationStatus.QUEUED,
                PublicationStatus.FAILED,
                PublicationUpdate(
                    error_code="PUBLISHING_QUEUE_ERROR",
                    error_message="The publication could not be queued.",
                ),
            )
            raise ApplicationError(
                code="PUBLISHING_QUEUE_ERROR",
                message="The publication could not be queued.",
                status_code=503,
            )
        return queued

    @staticmethod
    def _validate_schedule(scheduled_at: datetime | None, now: datetime) -> datetime | None:
        if scheduled_at is None:
            return None
        if scheduled_at.tzinfo is None or scheduled_at.utcoffset() is None:
            raise ApplicationError(
                code="INVALID_SCHEDULE_TIMEZONE",
                message="scheduled_at must include a timezone offset.",
                status_code=422,
            )
        normalized = scheduled_at.astimezone(UTC)
        if normalized <= now:
            raise ApplicationError(
                code="SCHEDULE_IN_PAST",
                message="scheduled_at must be in the future.",
                status_code=422,
            )
        return normalized

    @staticmethod
    def _invalid_state() -> ApplicationError:
        return ApplicationError(
            code="INVALID_PUBLICATION_STATE",
            message="Only pending publications can be queued.",
            status_code=409,
        )
