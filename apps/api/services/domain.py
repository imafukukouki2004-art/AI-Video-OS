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
)
from apps.api.domain.schemas import (
    JobCreate,
    ProjectCreate,
    ProjectUpdate,
    VideoCreate,
    WorkflowCreate,
    WorkflowExecutionCreate,
)
from apps.api.repositories import (
    JobRepository,
    ProjectRepository,
    VideoRepository,
    WorkflowExecutionRepository,
    WorkflowRepository,
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

    def __init__(self, repository: WorkflowRepository) -> None:
        super().__init__(repository)


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
