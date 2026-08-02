"""Celery application configured with Redis transport."""

from celery import Celery

from apps.api.config import Settings, get_settings


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Create a Celery application without opening broker connections."""

    application_settings = settings or get_settings()
    app = Celery(
        "ai-video-os-worker",
        broker=application_settings.celery_broker_url.get_secret_value(),
        backend=application_settings.celery_result_backend.get_secret_value(),
        include=["apps.worker.tasks"],
    )
    app.conf.update(
        accept_content=["json"],
        broker_connection_retry_on_startup=True,
        enable_utc=True,
        result_serializer="json",
        task_acks_late=True,
        task_default_queue="ai-video-os",
        task_reject_on_worker_lost=True,
        task_serializer="json",
        timezone="UTC",
        worker_prefetch_multiplier=1,
    )
    return app


celery_app = create_celery_app()
