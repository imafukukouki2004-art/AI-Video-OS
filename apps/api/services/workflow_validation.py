"""Application service for workflow definition validation."""

from uuid import UUID

from fastapi import status

from apps.api.domain.schemas import WorkflowValidationResult
from apps.api.errors.exceptions import ApplicationError
from apps.api.repositories import WorkflowRepository, WorkflowStepRepository
from apps.api.workflow.validator import WorkflowValidator


class WorkflowValidationService:
    """Service for validating workflow structures and configurations."""

    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        step_repository: WorkflowStepRepository,
    ) -> None:
        self.workflow_repository = workflow_repository
        self.step_repository = step_repository
        self.validator = WorkflowValidator()

    async def validate_workflow(self, workflow_id: UUID) -> WorkflowValidationResult:
        """
        Validate a workflow definition by its ID.
        """
        workflow = await self.workflow_repository.get_by_id(workflow_id)
        if not workflow:
            raise ApplicationError(
                code="WORKFLOW_NOT_FOUND",
                message="Workflow not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        steps = await self.step_repository.list_by_workflow(workflow_id)
        return await self.validator.validate(workflow, list(steps))
