"""FastAPI routers for core domain entities."""

from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import select

from apps.api.dependencies import DatabaseSessionDependency
from apps.api.domain.models import Job, Project, Video, Workflow
from apps.api.domain.schemas import (
    JobCreate,
    JobResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    VideoCreate,
    VideoResponse,
    WorkflowCreate,
    WorkflowResponse,
)
from apps.api.errors.exceptions import ApplicationError

router = APIRouter(tags=["domain"])


# --- Projects ---


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate, session: DatabaseSessionDependency
) -> ProjectResponse:
    """Create a new video production project."""
    project = Project(**project_in.model_dump())
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: UUID, session: DatabaseSessionDependency) -> ProjectResponse:
    """Retrieve a project by ID."""
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise ApplicationError(
            code="PROJECT_NOT_FOUND",
            message="Project not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return ProjectResponse.model_validate(project)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID, project_in: ProjectUpdate, session: DatabaseSessionDependency
) -> ProjectResponse:
    """Update an existing project."""
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise ApplicationError(
            code="PROJECT_NOT_FOUND",
            message="Project not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    update_data = project_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await session.commit()
    await session.refresh(project)
    return ProjectResponse.model_validate(project)


# --- Videos ---


@router.post("/videos", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def create_video(video_in: VideoCreate, session: DatabaseSessionDependency) -> VideoResponse:
    """Create a new video entity linked to a project."""
    video = Video(**video_in.model_dump())
    session.add(video)
    await session.commit()
    await session.refresh(video)
    return VideoResponse.model_validate(video)


@router.get("/videos/{video_id}", response_model=VideoResponse)
async def get_video(video_id: UUID, session: DatabaseSessionDependency) -> VideoResponse:
    """Retrieve a video by ID."""
    result = await session.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise ApplicationError(
            code="VIDEO_NOT_FOUND",
            message="Video not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return VideoResponse.model_validate(video)


# --- Workflows ---


@router.post("/workflows", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow_in: WorkflowCreate, session: DatabaseSessionDependency
) -> WorkflowResponse:
    """Create a new workflow configuration for a project."""
    workflow = Workflow(**workflow_in.model_dump())
    session.add(workflow)
    await session.commit()
    await session.refresh(workflow)
    return WorkflowResponse.model_validate(workflow)


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: UUID, session: DatabaseSessionDependency) -> WorkflowResponse:
    """Retrieve a workflow by ID."""
    result = await session.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise ApplicationError(
            code="WORKFLOW_NOT_FOUND",
            message="Workflow not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return WorkflowResponse.model_validate(workflow)


# --- Jobs ---


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(job_in: JobCreate, session: DatabaseSessionDependency) -> JobResponse:
    """Create a new AI job execution linked to a workflow."""
    job = Job(**job_in.model_dump())
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return JobResponse.model_validate(job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID, session: DatabaseSessionDependency) -> JobResponse:
    """Retrieve a job by ID."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise ApplicationError(
            code="JOB_NOT_FOUND",
            message="Job not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return JobResponse.model_validate(job)
