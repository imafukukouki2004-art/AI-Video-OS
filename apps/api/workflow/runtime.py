"""Workflow runtime for orchestrating job execution with state tracking."""

import logging
import time
from datetime import UTC, datetime
from typing import Any

from apps.api.ai_providers import AIProviderFactory
from apps.api.assets.schemas import AssetCreate
from apps.api.domain.models import (
    JobStatus,
    Workflow,
    WorkflowExecutionStatus,
    WorkflowStepStatus,
)
from apps.api.domain.schemas import (
    JobCreate,
    WorkflowArtifactCreate,
    WorkflowExecutionCreate,
    WorkflowExecutionErrorCreate,
    WorkflowExecutionHistoryCreate,
    WorkflowExecutionMetricCreate,
)
from apps.api.repositories import (
    AssetRepository,
    JobRepository,
    WorkflowArtifactRepository,
    WorkflowExecutionErrorRepository,
    WorkflowExecutionHistoryRepository,
    WorkflowExecutionMetricRepository,
    WorkflowExecutionRepository,
    WorkflowStepRepository,
)
from apps.api.workflow.context import VariableResolver, WorkflowContext
from apps.api.workflow.evaluator import ConditionEvaluator
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
        artifact_repository: WorkflowArtifactRepository,
        asset_repository: AssetRepository,
    ) -> None:
        self.job_repository = job_repository
        self.execution_repository = execution_repository
        self.step_repository = step_repository
        self.history_repository = history_repository
        self.error_repository = error_repository
        self.metric_repository = metric_repository
        self.artifact_repository = artifact_repository
        self.asset_repository = asset_repository
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

    async def _record_artifact(
        self,
        execution_id: Any,
        step_id: Any,
        artifact_type: str,
        asset_id: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        artifact_in = WorkflowArtifactCreate(
            workflow_execution_id=execution_id,
            workflow_step_id=step_id,
            artifact_type=artifact_type,
            asset_id=asset_id,
            metadata_data=metadata or {},
        )
        return await self.artifact_repository.create(artifact_in)

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

        # Create a map for quick lookup and keep a sorted list for sequential fallback
        steps_list = list(steps)
        steps_map = {step.id: step for step in steps_list}
        current_step = steps_list[0] if steps_list else None

        while current_step:
            step = current_step
            logger.info(f"Executing step: {step.name} (ID: {step.id}) in execution {execution.id}")

            job = None
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

                # Loop Handling
                items = [None]  # Default to single execution
                loop_var = None
                if step.loop_source:
                    try:
                        source_data = resolver.resolve_to_any(step.loop_source)
                        if not isinstance(source_data, list):
                            raise ValueError(f"Loop source must be a list, got {type(source_data)}")
                        items = source_data
                        loop_var = step.loop_variable or "item"
                        logger.info(f"Starting loop for step {step.name} with {len(items)} items")
                    except ValueError as e:
                        logger.error(f"Loop source resolution failed for step {step.id}: {e!s}")
                        raise ValueError(f"Loop resolution failed: {e!s}") from e

                iteration_results: list[Any] = []
                for item in items:
                    if loop_var:
                        context.set_step_output(loop_var, item)

                    # 6. Create Job (PENDING) linked to execution and step
                    job_in = JobCreate(
                        workflow_id=workflow.id,
                        step_id=step.id,
                        execution_id=execution.id,
                        name=f"{step.name} (Iteration)" if loop_var else step.name,
                        input_data={**step.config, "loop_item": item} if loop_var else step.config,
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

                    result_data: dict[str, Any] = {}
                    if operation == "text_generation":
                        # Input Mapping
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

                        # 9. Update Job to COMPLETED
                        result_data = {
                            "result": ai_res.content,
                            "metadata": ai_res.metadata,
                        }
                        iteration_results.append(ai_res.content)

                        # Artifact Handling
                        if ai_res.artifact_type:
                            artifact = await self._record_artifact(
                                execution_id=execution.id,
                                step_id=step.id,
                                artifact_type=ai_res.artifact_type,
                                asset_id=ai_res.asset_id,
                                metadata=ai_res.metadata,
                            )
                            # Register in context
                            context.set_step_artifact(str(step.id), artifact.id)
                            context.set_step_artifact(step.name, artifact.id)

                        if ai_res.asset_id:
                            context.set_step_asset(str(step.id), ai_res.asset_id)
                            context.set_step_asset(step.name, ai_res.asset_id)

                    elif operation == "image_generation":
                        # 1. Image Generation
                        prompt_raw = step.config.get("prompt", step.name)
                        try:
                            prompt = resolver.resolve(prompt_raw)
                        except ValueError as e:
                            logger.error(f"Variable resolution failed for step {step.id}: {e!s}")
                            raise ValueError(f"Variable resolution failed: {e!s}") from e

                        # Prepare call arguments
                        exclude_keys = ["provider", "operation", "prompt"]
                        call_kwargs = {
                            k: v for k, v in step.config.items() if k not in exclude_keys
                        }

                        # AI Execution
                        ai_res_img = await provider.generate_image(prompt=prompt, **call_kwargs)

                        # 2. Response Validation
                        if not ai_res_img.image_url and not ai_res_img.image_bytes:
                            raise ValueError("AI Provider returned empty image response")

                        # 3. Asset Registration (No real file storage for now)
                        asset_in = AssetCreate(
                            filename=f"generated_{int(time.time())}.png",
                            content_type=ai_res_img.mime_type or "image/png",
                            size_bytes=0,  # Unknown size for URL-based assets
                            object_key=f"generated/{execution.id}/{step.id}_{int(time.time())}.png",
                        )
                        asset = await self.asset_repository.create(asset_in)

                        # 4. WorkflowArtifact Registration
                        artifact = await self._record_artifact(
                            execution_id=execution.id,
                            step_id=step.id,
                            artifact_type="image",
                            asset_id=asset.id,
                            metadata=ai_res_img.metadata,
                        )

                        # 5. Context Registration (Post-Artifact Completion)
                        context.set_step_image(str(step.id), ai_res_img.image_url or "")
                        context.set_step_image(step.name, ai_res_img.image_url or "")
                        context.set_step_artifact(str(step.id), artifact.id)
                        context.set_step_artifact(step.name, artifact.id)
                        context.set_step_asset(str(step.id), asset.id)
                        context.set_step_asset(step.name, asset.id)

                        result_data = {
                            "image_url": ai_res_img.image_url,
                            "asset_id": str(asset.id),
                            "artifact_id": str(artifact.id),
                            "metadata": ai_res_img.metadata,
                        }
                        iteration_results.append(result_data)

                    else:
                        logger.error(f"Unsupported operation: {operation}")
                        raise ValueError(f"Unsupported AI operation: {operation}")

                    updated_job = await self.job_repository.update(
                        job.id,
                        {"status": JobStatus.COMPLETED, "output_data": result_data},
                    )
                    if updated_job:
                        job = updated_job
                    executed_jobs.append(job)
                    success_count += 1

                # Register final output in context
                final_output = iteration_results if step.loop_source else iteration_results[0]
                context.set_step_output(str(step.id), final_output)
                context.set_step_output(step.name, final_output)

                # 6. Step Completion
                await self.step_repository.update(step.id, {"status": WorkflowStepStatus.COMPLETED})
                await self._record_history(
                    execution.id,
                    "running",
                    "completed",
                    step_id=step.id,
                    message=f"Step {step.name} completed",
                )

                # Determine next step
                next_step = None
                if step.condition:
                    evaluator = ConditionEvaluator(resolver)
                    try:
                        condition_result = evaluator.evaluate(step.condition)
                        logger.info(
                            f"Condition evaluation result for step {step.name}: {condition_result}"
                        )

                        next_step_id = (
                            step.next_step_on_true if condition_result else step.next_step_on_false
                        )
                        if next_step_id:
                            next_step = steps_map.get(next_step_id)
                            if not next_step:
                                raise ValueError(
                                    f"Target step {next_step_id} not found in workflow"
                                )
                    except ValueError as e:
                        logger.error(f"Condition evaluation failed for step {step.id}: {e!s}")
                        raise ValueError(f"Condition evaluation failed: {e!s}") from e

                # Sequential fallback
                if not next_step:
                    try:
                        current_index = steps_list.index(step)
                        if current_index + 1 < len(steps_list):
                            next_step = steps_list[current_index + 1]
                    except ValueError:
                        pass

                current_step = next_step

            except Exception as e:
                failure_count += 1
                logger.exception(f"Step {step.id} failed in execution {execution.id}")

                # Update Step to FAILED
                await self.step_repository.update(step.id, {"status": WorkflowStepStatus.FAILED})

                # Record Error
                error_message = str(e) or "Unknown error occurred during step execution"
                await self._record_error(
                    execution.id,
                    "STEP_EXECUTION_FAILED",
                    error_message,
                    type(e).__name__,
                    step_id=step.id,
                )

                # Update current Job to FAILED if it exists and is still running
                if job:
                    await self.job_repository.update(job.id, {"status": JobStatus.FAILED})

                # Terminate workflow execution on failure
                await self.execution_repository.update(
                    execution.id,
                    {"status": WorkflowExecutionStatus.FAILED, "failed_at": datetime.now(UTC)},
                )
                await self._record_history(
                    execution.id,
                    str(execution.status),
                    "failed",
                    step_id=step.id,
                    message=f"Step {step.name} failed: {e!s}",
                )

                # Record metrics before returning
                duration_ms = (time.perf_counter() - start_time) * 1000
                await self._record_metric(execution.id, "duration_ms", duration_ms)
                await self._record_metric(execution.id, "step_count", len(executed_jobs))
                await self._record_metric(execution.id, "success_count", success_count)
                await self._record_metric(execution.id, "failure_count", failure_count)

                return {
                    "status": "failed",
                    "error": str(e),
                    "execution_id": execution.id,
                }

        # 10. Update Execution to COMPLETED
        await self.execution_repository.update(
            execution.id,
            {"status": WorkflowExecutionStatus.COMPLETED, "completed_at": datetime.now(UTC)},
        )
        await self._record_history(
            execution.id, str(execution.status), "completed", message="Execution completed"
        )

        # 11. Record Metrics
        duration_ms = (time.perf_counter() - start_time) * 1000
        await self._record_metric(execution.id, "duration_ms", duration_ms)
        await self._record_metric(execution.id, "step_count", len(executed_jobs))
        await self._record_metric(execution.id, "success_count", success_count)
        await self._record_metric(execution.id, "failure_count", failure_count)

        return {
            "status": "completed",
            "execution_id": execution.id,
            "duration_ms": duration_ms,
        }
