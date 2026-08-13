"""Foundation-only Celery task used to validate worker wiring."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, TypedDict
from uuid import UUID

from apps.api.config import get_settings
from apps.api.database.manager import Database
from apps.api.domain.models import WorkflowExecutionStatus
from apps.api.repositories import (
    AssetRepository,
    JobRepository,
    WorkflowArtifactRepository,
    WorkflowExecutionErrorRepository,
    WorkflowExecutionHistoryRepository,
    WorkflowExecutionMetricRepository,
    WorkflowExecutionRepository,
    WorkflowRepository,
    WorkflowStepRepository,
)
from apps.api.services.prompt_builder import PromptBuilder
from apps.api.storage.adapter import S3ObjectStorage
from apps.api.video_rendering import FFmpegVideoRenderer
from apps.api.workflow.runtime import WorkflowRuntime
from apps.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


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


@celery_app.task(name="apps.worker.tasks.execute_workflow_execution")  # type: ignore[misc]
def execute_workflow_execution(execution_id_str: str) -> dict[str, Any]:
    """Celery task to execute a workflow by its execution ID."""
    return asyncio.run(_execute_workflow_execution_async(execution_id_str))


async def _execute_workflow_execution_async(execution_id_str: str) -> dict[str, Any]:
    """Async implementation of workflow execution task."""
    execution_id = UUID(execution_id_str)
    settings = get_settings()
    db = Database(settings)

    # Initialize storage
    storage = S3ObjectStorage(settings)

    async with db.session_factory() as session:
        # Initialize repositories
        workflow_repo = WorkflowRepository(session)
        job_repo = JobRepository(session)
        execution_repo = WorkflowExecutionRepository(session)
        step_repo = WorkflowStepRepository(session)
        history_repo = WorkflowExecutionHistoryRepository(session)
        error_repo = WorkflowExecutionErrorRepository(session)
        metric_repo = WorkflowExecutionMetricRepository(session)
        artifact_repo = WorkflowArtifactRepository(session)
        asset_repo = AssetRepository(session)

        # Initialize runtime dependencies while the database session is active.
        runtime = WorkflowRuntime(
            job_repo,
            execution_repo,
            step_repo,
            history_repo,
            error_repo,
            metric_repo,
            artifact_repo,
            asset_repo,
            storage,
            PromptBuilder(),
            FFmpegVideoRenderer(),
        )

        # Get the execution record
        execution = await execution_repo.get_by_id(execution_id)
        if not execution:
            logger.error(f"Execution {execution_id} not found")
            return {"status": "failed", "error": "Execution not found"}

        # Get the associated workflow
        workflow = await workflow_repo.get_by_id(execution.workflow_id)
        if not workflow:
            logger.error(f"Workflow {execution.workflow_id} not found for execution {execution_id}")
            return {"status": "failed", "error": "Workflow not found"}

        # Trigger execution
        logger.info(f"Worker starting execution {execution_id} for workflow {workflow.id}")
        try:
            result = await runtime.run(workflow, execution_id=execution_id)
            logger.info(
                f"Worker completed execution {execution_id} with status {result.get('status')}"
            )
            return result
        except Exception as e:
            logger.exception(f"Unexpected error in worker for execution {execution_id}")
            # Final safety update to FAILED if runtime failed to catch it
            await execution_repo.update(
                execution_id,
                {"status": WorkflowExecutionStatus.FAILED, "failed_at": datetime.now(UTC)},
            )
            return {"status": "failed", "error": str(e)}
        finally:
            # Worker cleanup - Dispose database engine and close storage
            await storage.close()
            await db.dispose()
