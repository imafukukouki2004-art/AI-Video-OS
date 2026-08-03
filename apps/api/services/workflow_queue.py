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

    async def enqueue_workflow(self, workflow_id: UUID) -> tuple[UUID, str]:
        """Create an execution record and dispatch it to the Celery worker."""
        logger.info(f"Enqueuing workflow {workflow_id}")

        # 1. Create WorkflowExecution in PENDING state
        from apps.api.domain.schemas import WorkflowExecutionCreate
        execution_in = WorkflowExecutionCreate(workflow_id=workflow_id)
        execution = await self.execution_repository.create(execution_in)

        # 2. Dispatch the workflow execution task to the worker
        task = celery_app.send_task(
            "apps.worker.tasks.execute_workflow_execution",
            args=[str(execution.id)],
            queue="ai-video-os",
        )

        # 3. Save the task ID to the execution record
        await self.execution_repository.update(execution.id, {"task_id": task.id})

        logger.info(
            f"Workflow {workflow_id} enqueued as execution {execution.id} with task_id {task.id}"
        )
        return execution.id, str(task.id)

    async def enqueue_execution(self, execution_id: UUID) -> str:
        """Dispatch an existing workflow execution to the Celery worker."""
        logger.info(f"Dispatching existing execution {execution_id} to queue")

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
