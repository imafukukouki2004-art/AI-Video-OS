"""Service for managing workflow execution queue."""

import logging
from uuid import UUID

from apps.api.repositories import WorkflowExecutionRepository
from apps.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


class WorkflowQueueService:
    """Service for dispatching workflow executions to Celery queue."""

    def __init__(self, execution_repository: WorkflowExecutionRepository) -> None:
        self.execution_repository = execution_repository

    async def enqueue_execution(self, execution_id: UUID) -> str:
        """Dispatch a workflow execution to the Celery worker."""
        logger.info(f"Dispatching execution {execution_id} to queue")

        # Dispatch the workflow execution task to the worker
        task = celery_app.send_task(
            "apps.worker.tasks.execute_workflow_execution",
            args=[str(execution_id)],
            queue="ai-video-os",
        )
        
        # Save the task ID to the execution record
        await self.execution_repository.update(execution_id, {"task_id": task.id})
        
        logger.info(f"Execution {execution_id} enqueued with task_id {task.id}")
        return str(task.id)

    async def get_task_status(self, task_id: str) -> str:
        """Retrieve the status of a Celery task."""
        result = celery_app.AsyncResult(task_id)
        return str(result.status)
