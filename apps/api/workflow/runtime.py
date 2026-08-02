"""Workflow runtime for orchestrating job execution with state tracking."""

import logging
from datetime import UTC, datetime
from typing import Any

from apps.api.domain.models import (
    JobStatus,
    Workflow,
    WorkflowExecutionStatus,
    WorkflowStepStatus,
)
from apps.api.domain.schemas import (
    JobCreate,
    WorkflowExecutionCreate,
    WorkflowExecutionHistoryCreate,
)
from apps.api.repositories import (
    JobRepository,
    WorkflowExecutionHistoryRepository,
    WorkflowExecutionRepository,
    WorkflowStepRepository,
)

logger = logging.getLogger(__name__)


class WorkflowRuntime:
    """Synchronous workflow runtime with execution state tracking and history."""

    def __init__(
        self,
        job_repository: JobRepository,
        execution_repository: WorkflowExecutionRepository,
        step_repository: WorkflowStepRepository,
        history_repository: WorkflowExecutionHistoryRepository,
    ) -> None:
        self.job_repository = job_repository
        self.execution_repository = execution_repository
        self.step_repository = step_repository
        self.history_repository = history_repository

    async def _record_history(
        self,
        execution_id: Any,
        from_status: str,
        to_status: str,
        step_id: Any | None = None,
        message: str | None = None,
    ) -> None:
        history_in = WorkflowExecutionHistoryCreate(
            workflow_execution_id=execution_id,
            workflow_step_id=step_id,
            from_status=from_status,
            to_status=to_status,
            message=message,
        )
        await self.history_repository.create(history_in)

    async def run(self, workflow: Workflow) -> dict[str, Any]:
        """
        Execute a workflow synchronously and track its state and history.
        """
        logger.info(f"Starting workflow runtime for workflow: {workflow.id}")

        # 1. Create WorkflowExecution (PENDING)
        execution_in = WorkflowExecutionCreate(workflow_id=workflow.id)
        execution = await self.execution_repository.create(execution_in)

        # 2. Update Execution to RUNNING
        from_status = str(execution.status)
        updated_execution = await self.execution_repository.update(
            execution.id,
            {"status": WorkflowExecutionStatus.RUNNING, "started_at": datetime.now(UTC)},
        )
        if not updated_execution:
            return {"status": "failed", "error": "Failed to initialize execution"}
        execution = updated_execution

        await self._record_history(
            execution.id, from_status, str(execution.status), message="Execution started"
        )

        # 3. Retrieve Steps from Repository
        steps = await self.step_repository.list_by_workflow(workflow.id)
        if not steps:
            logger.warning(f"No steps defined for workflow {workflow.id}")
            from_status = str(execution.status)
            await self.execution_repository.update(
                execution.id,
                {"status": WorkflowExecutionStatus.COMPLETED, "completed_at": datetime.now(UTC)},
            )
            await self._record_history(
                execution.id, from_status, "completed", message="Completed with no steps"
            )
            return {"status": "completed", "jobs": [], "execution_id": execution.id}

        executed_jobs = []

        for step in steps:
            logger.info(f"Executing step: {step.name} (ID: {step.id}) in execution {execution.id}")

            try:
                # 4. Update Step to RUNNING
                from_step_status = str(step.status)
                await self.step_repository.update(step.id, {"status": WorkflowStepStatus.RUNNING})
                await self._record_history(
                    execution.id,
                    from_step_status,
                    "running",
                    step_id=step.id,
                    message=f"Step {step.name} started",
                )

                # 5. Create Job (PENDING) linked to execution and step
                job_in = JobCreate(
                    workflow_id=workflow.id,
                    step_id=step.id,
                    execution_id=execution.id,
                    name=step.name,
                    input_data=step.config,
                )
                job = await self.job_repository.create(job_in)

                # 6. Update Job to RUNNING
                updated_job = await self.job_repository.update(
                    job.id, {"status": JobStatus.RUNNING}
                )
                if updated_job:
                    job = updated_job

                # 7. Simulate Execution
                logger.info(f"Simulating execution for job {job.id}")

                # 8. Update Job and Step to COMPLETED
                result_data = {"result": f"Simulated output for {step.name}"}
                updated_job = await self.job_repository.update(
                    job.id,
                    {"status": JobStatus.COMPLETED, "output_data": result_data},
                )
                if updated_job:
                    job = updated_job

                await self.step_repository.update(step.id, {"status": WorkflowStepStatus.COMPLETED})
                await self._record_history(
                    execution.id,
                    "running",
                    "completed",
                    step_id=step.id,
                    message=f"Step {step.name} completed",
                )
                executed_jobs.append(job)

            except Exception as e:
                logger.error(f"Step {step.id} failed: {e!s}")
                # Note: job might not have been created yet if create failed
                # But we should still mark the step and execution as failed
                await self.step_repository.update(step.id, {"status": WorkflowStepStatus.FAILED})
                await self._record_history(
                    execution.id,
                    "running",
                    "failed",
                    step_id=step.id,
                    message=f"Step {step.name} failed: {e!s}",
                )

                # Update Execution to FAILED
                from_exec_status = str(execution.status)
                await self.execution_repository.update(
                    execution.id,
                    {"status": WorkflowExecutionStatus.FAILED, "failed_at": datetime.now(UTC)},
                )
                await self._record_history(
                    execution.id, from_exec_status, "failed", message=f"Execution failed: {e!s}"
                )

                return {
                    "status": "failed",
                    "error": str(e),
                    "execution_id": execution.id,
                    "completed_jobs": [j.id for j in executed_jobs],
                }

        # 9. Update Execution to COMPLETED
        logger.info(f"Workflow {workflow.id} completed successfully (Execution: {execution.id})")
        from_exec_status = str(execution.status)
        await self.execution_repository.update(
            execution.id,
            {"status": WorkflowExecutionStatus.COMPLETED, "completed_at": datetime.now(UTC)},
        )
        await self._record_history(
            execution.id, from_exec_status, "completed", message="Execution completed successfully"
        )

        return {
            "status": "completed",
            "execution_id": execution.id,
            "jobs": [j.id for j in executed_jobs],
        }
