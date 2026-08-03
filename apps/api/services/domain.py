"""Domain-specific application services."""

from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID

from apps.api.domain.models import (
    Job,
    Project,
    Video,
    Workflow,
    WorkflowExecution,
    WorkflowExecutionError,
    WorkflowExecutionHistory,
    WorkflowExecutionMetric,
    WorkflowStep,
)
from apps.api.domain.schemas import (
    JobCreate,
    ProjectCreate,
    ProjectUpdate,
    VideoCreate,
    WorkflowCreate,
    WorkflowExecutionCreate,
    WorkflowExecutionErrorCreate,
    WorkflowExecutionHistoryCreate,
    WorkflowExecutionMetricCreate,
    WorkflowStepCreate,
)
from apps.api.repositories import (
    JobRepository,
    ProjectRepository,
    VideoRepository,
    WorkflowExecutionErrorRepository,
    WorkflowExecutionHistoryRepository,
    WorkflowExecutionMetricRepository,
    WorkflowExecutionRepository,
    WorkflowRepository,
    WorkflowStepRepository,
)
from apps.api.services.base import BaseService


class ProjectService(BaseService[Project, ProjectCreate, ProjectUpdate]):
    """Service for project-related use cases."""

    def __init__(self, repository: ProjectRepository) -> None:
        super().__init__(repository)


class VideoService(BaseService[Video, VideoCreate, Any]):
    """Service for video-related use cases."""

    def __init__(self, repository: VideoRepository) -> None:
        super().__init__(repository)


class WorkflowService(BaseService[Workflow, WorkflowCreate, Any]):
    """Service for workflow-related use cases."""

    def __init__(
        self, repository: WorkflowRepository, step_repository: WorkflowStepRepository
    ) -> None:
        super().__init__(repository)
        self.step_repository = step_repository

    async def list_steps(self, workflow_id: UUID) -> Sequence[WorkflowStep]:
        """Retrieve all steps for a workflow ordered by execution order."""
        return await self.step_repository.list_by_workflow(workflow_id)


class WorkflowStepService(BaseService[WorkflowStep, WorkflowStepCreate, Any]):
    """Service for workflow step management."""

    def __init__(self, repository: WorkflowStepRepository) -> None:
        super().__init__(repository)

    async def list_by_workflow(self, workflow_id: UUID) -> Sequence[WorkflowStep]:
        repo = cast(WorkflowStepRepository, self.repository)
        return await repo.list_by_workflow(workflow_id)


class JobService(BaseService[Job, JobCreate, Any]):
    """Service for job-related use cases."""

    def __init__(self, repository: JobRepository) -> None:
        super().__init__(repository)


class WorkflowExecutionService(BaseService[WorkflowExecution, WorkflowExecutionCreate, Any]):
    """Service for workflow execution tracking."""

    def __init__(self, repository: WorkflowExecutionRepository) -> None:
        super().__init__(repository)

    async def list_by_workflow(self, workflow_id: UUID) -> Sequence[WorkflowExecution]:
        repo = cast(WorkflowExecutionRepository, self.repository)
        return await repo.list_by_workflow(workflow_id)


class WorkflowExecutionHistoryService(
    BaseService[WorkflowExecutionHistory, WorkflowExecutionHistoryCreate, Any]
):
    """Service for workflow execution audit trails."""

    def __init__(self, repository: WorkflowExecutionHistoryRepository) -> None:
        super().__init__(repository)

    async def list_by_execution(self, execution_id: UUID) -> Sequence[WorkflowExecutionHistory]:
        repo = cast(WorkflowExecutionHistoryRepository, self.repository)
        return await repo.list_by_execution(execution_id)

    async def list_by_step(self, step_id: UUID) -> Sequence[WorkflowExecutionHistory]:
        repo = cast(WorkflowExecutionHistoryRepository, self.repository)
        return await repo.list_by_step(step_id)


class WorkflowExecutionErrorService(
    BaseService[WorkflowExecutionError, WorkflowExecutionErrorCreate, Any]
):
    """Service for workflow execution error management."""

    def __init__(self, repository: WorkflowExecutionErrorRepository) -> None:
        super().__init__(repository)

    async def list_by_execution(self, execution_id: UUID) -> Sequence[WorkflowExecutionError]:
        repo = cast(WorkflowExecutionErrorRepository, self.repository)
        return await repo.list_by_execution(execution_id)

    async def list_by_step(self, step_id: UUID) -> Sequence[WorkflowExecutionError]:
        repo = cast(WorkflowExecutionErrorRepository, self.repository)
        return await repo.list_by_step(step_id)


class WorkflowExecutionMetricService(
    BaseService[WorkflowExecutionMetric, WorkflowExecutionMetricCreate, Any]
):
    """Service for workflow execution metric management."""

    def __init__(self, repository: WorkflowExecutionMetricRepository) -> None:
        super().__init__(repository)

    async def list_by_execution(self, execution_id: UUID) -> Sequence[WorkflowExecutionMetric]:
        repo = cast(WorkflowExecutionMetricRepository, self.repository)
        return await repo.list_by_execution(execution_id)

    async def list_by_type(
        self, execution_id: UUID, metric_type: str
    ) -> Sequence[WorkflowExecutionMetric]:
        repo = cast(WorkflowExecutionMetricRepository, self.repository)
        return await repo.list_by_type(execution_id, metric_type)
