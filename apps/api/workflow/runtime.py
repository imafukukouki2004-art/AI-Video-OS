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
from apps.api.domain.schemas import JobCreate, WorkflowExecutionCreate
from apps.api.repositories import (
    JobRepository,
    WorkflowExecutionRepository,
    WorkflowStepRepository,
)

logger = logging.getLogger(__name__)


class WorkflowRuntime:
    """Synchronous workflow runtime with execution state tracking and step definitions."""

    def __init__(
        self,
        job_repository: JobRepository,
        execution_repository: WorkflowExecutionRepository,
        step_repository: WorkflowStepRepository,
    ) -> None:
        self.job_repository = job_repository
        self.execution_repository = execution_repository
        self.step_repository = step_repository

    async def run(self, workflow: Workflow) -> dict[str, Any]:
        """
        Execute a workflow synchronously and track its state using persistent step definitions.
        """
        logger.info(f"Starting workflow runtime for workflow: {workflow.id}")

        # 1. Create WorkflowExecution (PENDING)
        execution_in = WorkflowExecutionCreate(workflow_id=workflow.id)
        execution = await self.execution_repository.create(execution_in)

        # 2. Update Execution to RUNNING
        updated_execution = await self.execution_repository.update(
            execution.id,
            {"status": WorkflowExecutionStatus.RUNNING, "started_at": datetime.now(UTC)},
        )
        if not updated_execution:
            return {"status": "failed", "error": "Failed to initialize execution"}
        execution = updated_execution

        # 3. Retrieve Steps from Repository
        steps = await self.step_repository.list_by_workflow(workflow.id)
        if not steps:
            logger.warning(f"No steps defined for workflow {workflow.id}")
            await self.execution_repository.update(
                execution.id,
                {"status": WorkflowExecutionStatus.COMPLETED, "completed_at": datetime.now(UTC)},
            )
            return {"status": "completed", "jobs": [], "execution_id": execution.id}

        executed_jobs = []

        for step in steps:
            logger.info(f"Executing step: {step.name} (ID: {step.id}) in execution {execution.id}")

            # 4. Update Step to RUNNING
            await self.step_repository.update(step.id, {"status": WorkflowStepStatus.RUNNING})

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
            updated_job = await self.job_repository.update(job.id, {"status": JobStatus.RUNNING})
            if updated_job:
                job = updated_job

            try:
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
                executed_jobs.append(job)

            except Exception as e:
                logger.error(f"Step {step.id} / Job {job.id} failed: {e!s}")
                await self.job_repository.update(job.id, {"status": JobStatus.FAILED})
                await self.step_repository.update(step.id, {"status": WorkflowStepStatus.FAILED})

                # Update Execution to FAILED
                await self.execution_repository.update(
                    execution.id,
                    {"status": WorkflowExecutionStatus.FAILED, "failed_at": datetime.now(UTC)},
                )

                return {
                    "status": "failed",
                    "error": str(e),
                    "execution_id": execution.id,
                    "completed_jobs": [j.id for j in executed_jobs],
                }

        # 9. Update Execution to COMPLETED
        logger.info(f"Workflow {workflow.id} completed successfully (Execution: {execution.id})")
        await self.execution_repository.update(
            execution.id,
            {"status": WorkflowExecutionStatus.COMPLETED, "completed_at": datetime.now(UTC)},
        )

        return {
            "status": "completed",
            "execution_id": execution.id,
            "jobs": [j.id for j in executed_jobs],
        }
