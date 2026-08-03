"""Workflow runtime for orchestrating job execution with state tracking."""

import logging
import time
from datetime import UTC, datetime
from typing import Any

from apps.api.ai_providers import AIProviderFactory
from apps.api.domain.models import (
    JobStatus,
    Workflow,
    WorkflowExecutionStatus,
    WorkflowStepStatus,
)
from apps.api.domain.schemas import (
    JobCreate,
    WorkflowExecutionCreate,
    WorkflowExecutionErrorCreate,
    WorkflowExecutionHistoryCreate,
    WorkflowExecutionMetricCreate,
)
from apps.api.repositories import (
    JobRepository,
    WorkflowExecutionErrorRepository,
    WorkflowExecutionHistoryRepository,
    WorkflowExecutionMetricRepository,
    WorkflowExecutionRepository,
    WorkflowStepRepository,
)
from apps.api.workflow.context import VariableResolver, WorkflowContext
from apps.api.workflow.validator import WorkflowValidator

logger = logging.getLogger(__name__)


class WorkflowRuntime:
    """Synchronous workflow runtime with execution state tracking, history, and metrics."""

    def __init__(
        self,
        job_repository: JobRepository,
        execution_repository: WorkflowExecutionRepository,
        step_repository: WorkflowStepRepository,
        history_repository: WorkflowExecutionHistoryRepository,
        error_repository: WorkflowExecutionErrorRepository,
        metric_repository: WorkflowExecutionMetricRepository,
    ) -> None:
        self.job_repository = job_repository
        self.execution_repository = execution_repository
        self.step_repository = step_repository
        self.history_repository = history_repository
        self.error_repository = error_repository
        self.metric_repository = metric_repository
        self.validator = WorkflowValidator()

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

    async def _record_error(
        self,
        execution_id: Any,
        error_code: str,
        message: str,
        error_type: str,
        step_id: Any | None = None,
    ) -> None:
        error_in = WorkflowExecutionErrorCreate(
            workflow_execution_id=execution_id,
            workflow_step_id=step_id,
            error_code=error_code,
            error_message=message,
            error_type=error_type,
        )
        await self.error_repository.create(error_in)

    async def _record_metric(self, execution_id: Any, metric_type: str, value: float) -> None:
        metric_in = WorkflowExecutionMetricCreate(
            workflow_execution_id=execution_id, metric_type=metric_type, metric_value=value
        )
        await self.metric_repository.create(metric_in)

    async def run(self, workflow: Workflow, execution_id: Any | None = None) -> dict[str, Any]:
        """
        Execute a workflow synchronously and track its state, history, and metrics.
        If execution_id is provided, use the existing execution record.
        """
        logger.info(f"Starting workflow runtime for workflow: {workflow.id}")
        start_time = time.perf_counter()

        # Initialize Workflow Context and Variable Resolver
        context = WorkflowContext()
        resolver = VariableResolver(context)

        # 1. Retrieve Steps from Repository
        steps = await self.step_repository.list_by_workflow(workflow.id)

        # 2. Validation Guard
        validation_result = await self.validator.validate(workflow, list(steps))
        if not validation_result.valid:
            logger.error(f"Workflow {workflow.id} validation failed: {validation_result.errors}")
            if execution_id:
                await self._record_error(
                    execution_id,
                    "VALIDATION_FAILED",
                    f"Workflow validation failed: {validation_result.errors}",
                    "ValidationError",
                )
                await self.execution_repository.update(
                    execution_id,
                    {"status": WorkflowExecutionStatus.FAILED, "failed_at": datetime.now(UTC)},
                )
            return {
                "status": "failed",
                "error": "Workflow validation failed",
                "validation_errors": validation_result.errors,
            }

        # 3. Create or Get WorkflowExecution
        if execution_id:
            execution = await self.execution_repository.get_by_id(execution_id)
            if not execution:
                return {"status": "failed", "error": f"Execution {execution_id} not found"}
        else:
            # 3. Create WorkflowExecution (PENDING)
            execution_in = WorkflowExecutionCreate(workflow_id=workflow.id)
            execution = await self.execution_repository.create(execution_in)

        # 4. Update Execution to RUNNING
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

        executed_jobs = []
        success_count = 0
        failure_count = 0

        for step in steps:
            logger.info(f"Executing step: {step.name} (ID: {step.id}) in execution {execution.id}")

            try:
                # 5. Update Step to RUNNING
                from_step_status = str(step.status)
                await self.step_repository.update(step.id, {"status": WorkflowStepStatus.RUNNING})
                await self._record_history(
                    execution.id,
                    from_step_status,
                    "running",
                    step_id=step.id,
                    message=f"Step {step.name} started",
                )

                # 6. Create Job (PENDING) linked to execution and step
                job_in = JobCreate(
                    workflow_id=workflow.id,
                    step_id=step.id,
                    execution_id=execution.id,
                    name=step.name,
                    input_data=step.config,
                )
                job = await self.job_repository.create(job_in)

                # 7. Update Job to RUNNING
                updated_job = await self.job_repository.update(
                    job.id, {"status": JobStatus.RUNNING}
                )
                if updated_job:
                    job = updated_job

                # 8. AI Provider Execution
                logger.info(f"Executing AI Provider for job {job.id} (Step: {step.name})")

                # Determine provider and operation from step config
                provider_name = step.config.get("provider", "mock")
                operation = step.config.get("operation", "text_generation")
                provider = AIProviderFactory.create(provider_name)

                if operation == "text_generation":
                    # Input Mapping: Map prompt and system_prompt from step config
                    # Default to step name if prompt is missing
                    prompt_raw = step.config.get("prompt", step.name)
                    system_prompt_raw = step.config.get("system_prompt")

                    # Variable Resolution
                    try:
                        prompt = resolver.resolve(prompt_raw)
                        system_prompt = (
                            resolver.resolve(system_prompt_raw) if system_prompt_raw else None
                        )
                    except ValueError as e:
                        logger.error(f"Variable resolution failed for step {step.id}: {e!s}")
                        raise ValueError(f"Variable resolution failed: {e!s}") from e

                    # Prepare call arguments
                    exclude_keys = ["provider", "operation", "prompt", "system_prompt"]
                    call_kwargs = {
                        k: v for k, v in step.config.items() if k not in exclude_keys
                    }
                    if system_prompt:
                        call_kwargs["system_prompt"] = system_prompt

                    # AI Execution
                    ai_res = await provider.generate_text(prompt=prompt, **call_kwargs)

                    # 9. Update Job and Step to COMPLETED
                    result_data = {
                        "result": ai_res.content,
                        "metadata": ai_res.metadata,
                    }

                    # Register output in context for subsequent steps
                    # Register by both ID and Name to support flexible variable resolution
                    context.set_step_output(str(step.id), ai_res.content)
                    context.set_step_output(step.name, ai_res.content)
                else:
                    logger.error(f"Unsupported operation: {operation}")
                    raise ValueError(f"Unsupported AI operation: {operation}")
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
                success_count += 1

            except Exception as e:
                logger.exception(f"Step {step.id} failed in execution {execution.id}")
                failure_count += 1

                # Integrated failure flow:
                # A. Create Error Record
                await self._record_error(
                    execution.id,
                    error_code="STEP_EXECUTION_FAILED",
                    message=str(e),
                    error_type=type(e).__name__,
                    step_id=step.id,
                )

                # Update Job to FAILED if it was created
                if "job" in locals() and job:
                    await self.job_repository.update(job.id, {"status": JobStatus.FAILED})

                # B. Update Step Status
                await self.step_repository.update(step.id, {"status": WorkflowStepStatus.FAILED})

                # C. Update Execution Status to FAILED
                from_exec_status = str(execution.status)
                await self.execution_repository.update(
                    execution.id,
                    {"status": WorkflowExecutionStatus.FAILED, "failed_at": datetime.now(UTC)},
                )

                # D. Record History
                await self._record_history(
                    execution.id,
                    "running",
                    "failed",
                    step_id=step.id,
                    message=f"Step {step.name} failed: {e!s}",
                )
                await self._record_history(
                    execution.id, from_exec_status, "failed", message=f"Execution failed: {e!s}"
                )

                # E. Record Metrics even on failure
                end_time = time.perf_counter()
                duration_ms = (end_time - start_time) * 1000
                await self._record_metric(execution.id, "duration_ms", duration_ms)
                await self._record_metric(execution.id, "step_count", float(len(steps)))
                await self._record_metric(execution.id, "success_count", float(success_count))
                await self._record_metric(execution.id, "failure_count", float(failure_count))

                return {
                    "status": "failed",
                    "error": str(e),
                    "execution_id": execution.id,
                    "completed_jobs": [j.id for j in executed_jobs],
                }

        # 10. Update Execution to COMPLETED
        logger.info(f"Workflow {workflow.id} completed successfully (Execution: {execution.id})")
        from_exec_status = str(execution.status)
        await self.execution_repository.update(
            execution.id,
            {"status": WorkflowExecutionStatus.COMPLETED, "completed_at": datetime.now(UTC)},
        )
        await self._record_history(
            execution.id, from_exec_status, "completed", message="Execution completed successfully"
        )

        # 11. Record Metrics
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000
        await self._record_metric(execution.id, "duration_ms", duration_ms)
        await self._record_metric(execution.id, "step_count", float(len(steps)))
        await self._record_metric(execution.id, "success_count", float(success_count))
        await self._record_metric(execution.id, "failure_count", float(failure_count))

        return {
            "status": "completed",
            "execution_id": execution.id,
            "jobs": [j.id for j in executed_jobs],
        }
