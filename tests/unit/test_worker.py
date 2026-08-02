"""Celery worker foundation tests."""

from apps.api.config import Settings
from apps.worker.celery_app import create_celery_app
from apps.worker.tasks import foundation_test


def test_celery_application_uses_redis_and_safe_defaults() -> None:
    app = create_celery_app(
        Settings(
            app_env="test",
            celery_broker_url="redis://cache:6379/0",
            celery_result_backend="redis://cache:6379/1",
            _env_file=None,
        )
    )

    assert app.conf.broker_url == "redis://cache:6379/0"
    assert app.conf.result_backend == "redis://cache:6379/1"
    assert app.conf.task_serializer == "json"
    assert app.conf.accept_content == ["json"]
    assert app.conf.task_acks_late is True
    assert app.conf.worker_prefetch_multiplier == 1
    assert app.conf.broker_connection_retry_on_startup is True


def test_foundation_task_is_registered_with_retry_policy() -> None:
    assert foundation_test.name == "apps.worker.tasks.foundation_test"
    assert foundation_test.max_retries == 3
    assert foundation_test.run("worker-ready") == {
        "status": "ok",
        "value": "worker-ready",
    }
