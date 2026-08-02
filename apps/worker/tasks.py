"""Foundation-only Celery task used to validate worker wiring."""

from typing import TypedDict

from apps.api.config import get_settings
from apps.worker.celery_app import celery_app


class FoundationTaskResult(TypedDict):
    status: str
    value: str


class FoundationRetryRequested(RuntimeError):
    """Signal used only to verify Celery automatic retry configuration."""


settings = get_settings()


@celery_app.task(  # type: ignore[misc]
    name="apps.worker.tasks.foundation_test",
    autoretry_for=(FoundationRetryRequested,),
    max_retries=settings.celery_task_max_retries,
    retry_backoff=True,
    retry_backoff_max=settings.celery_retry_backoff_max_seconds,
    retry_jitter=True,
)
def foundation_test(value: str = "ok", *, request_retry: bool = False) -> FoundationTaskResult:
    """Return a deterministic payload or request a retry for foundation tests."""

    if request_retry:
        raise FoundationRetryRequested("foundation retry requested")
    return {"status": "ok", "value": value}
