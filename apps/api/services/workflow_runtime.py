"""Application service for workflow runtime orchestration."""

from typing import Any
from uuid import UUID

from fastapi import status

from apps.api.errors.exceptions import ApplicationError
from apps.api.publishing.automatic import AutomaticPublishingCoordinator
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
from apps.api.storage import ObjectStorage
from apps.api.video_rendering import VideoRenderer
from apps.api.workflow.runtime import WorkflowRuntime


class WorkflowRuntimeService:
    """Service for orchestrating workflow execution."""

    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        job_repository: JobRepository,
        execution_repository: WorkflowExecutionRepository,
        step_repository: WorkflowStepRepository,
        history_repository: WorkflowExecutionHistoryRepository,
        error_repository: WorkflowExecutionErrorRepository,
        metric_repository: WorkflowExecutionMetricRepository,
        artifact_repository: WorkflowArtifactRepository,
        asset_repository: AssetRepository,
        storage: ObjectStorage,
        prompt_builder: PromptBuilder,
        video_renderer: VideoRenderer | None = None,
        automatic_publishing: AutomaticPublishingCoordinator | None = None,
    ) -> None:
        self.workflow_repository = workflow_repository
        self.automatic_publishing = automatic_publishing
        self.runtime = WorkflowRuntime(
            job_repository,
            execution_repository,
            step_repository,
            history_repository,
            error_repository,
            metric_repository,
            artifact_repository,
            asset_repository,
            storage,
            prompt_builder,
            video_renderer,
        )

    async def execute_workflow(self, workflow_id: UUID) -> dict[str, Any]:
        """Trigger synchronous execution of a workflow."""
        workflow = await self.workflow_repository.get_by_id(workflow_id)
        if not workflow:
            raise ApplicationError(
                code="WORKFLOW_NOT_FOUND",
                message="Workflow not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        result = await self.runtime.run(workflow)
        if self.automatic_publishing is not None and result.get("status") == "completed":
            execution_id = result.get("execution_id")
            if isinstance(execution_id, UUID):
                await self.automatic_publishing.handle_completion(workflow, execution_id)
        return result
