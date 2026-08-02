"""Domain-specific application services."""

from typing import Any

from apps.api.domain.models import Job, Project, Video, Workflow
from apps.api.domain.schemas import (
    JobCreate,
    ProjectCreate,
    ProjectUpdate,
    VideoCreate,
    WorkflowCreate,
)
from apps.api.repositories import (
    JobRepository,
    ProjectRepository,
    VideoRepository,
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
