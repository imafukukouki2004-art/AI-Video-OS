"""Workflow runtime for orchestrating job execution."""

import logging
from typing import Any

from apps.api.domain.models import JobStatus, Workflow
from apps.api.domain.schemas import JobCreate
from apps.api.repositories import JobRepository

logger = logging.getLogger(__name__)


class WorkflowRuntime:
    """Synchronous workflow runtime foundation."""

    def __init__(self, job_repository: JobRepository) -> None:
        self.job_repository = job_repository

    async def run(self, workflow: Workflow) -> dict[str, Any]:
        """
        Execute a workflow synchronously.

        This foundation implementation reads steps from workflow config,
        creates jobs, and simulates their execution.
        """
        logger.info(f"Starting workflow runtime for workflow: {workflow.id}")

        steps = workflow.config.get("steps", [])
        if not steps:
            logger.warning(f"No steps defined for workflow {workflow.id}")
            return {"status": "completed", "jobs": []}

        executed_jobs = []

        for step in steps:
            step_name = step.get("name", "unnamed_step")
            logger.info(f"Executing step: {step_name}")

            # 1. Create Job (PENDING)
            job_in = JobCreate(
                workflow_id=workflow.id, name=step_name, input_data=step.get("input", {})
            )
            job = await self.job_repository.create(job_in)

            # 2. Update to RUNNING
            # Note: In a real system, this would be handled by a worker.
            # Here we do it synchronously as per TICKET-013 scope.
            updated_job = await self.job_repository.update(
                job.id,
                {"status": JobStatus.RUNNING},
            )
            if updated_job:
                job = updated_job

            try:
                # 3. Simulate Execution
                # In future tickets, this will call AI Providers or Celery tasks.
                logger.info(f"Simulating execution for job {job.id}")

                # 4. Update to COMPLETED
                result_data = {"result": f"Simulated output for {step_name}"}
                updated_job = await self.job_repository.update(
                    job.id,
                    {"status": JobStatus.COMPLETED, "output_data": result_data},
                )
                if updated_job:
                    job = updated_job
                executed_jobs.append(job)

            except Exception as e:
                logger.error(f"Job {job.id} failed: {e!s}")
                await self.job_repository.update(
                    job.id,
                    {"status": JobStatus.FAILED},
                )
                return {
                    "status": "failed",
                    "error": str(e),
                    "completed_jobs": [j.id for j in executed_jobs],
                }

        logger.info(f"Workflow {workflow.id} completed successfully")
        return {"status": "completed", "jobs": [j.id for j in executed_jobs]}
