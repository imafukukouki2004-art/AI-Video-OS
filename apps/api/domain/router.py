"""FastAPI routers for core domain entities using services."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, status

from apps.api.dependencies import (
    JobServiceDependency,
    ProjectServiceDependency,
    VideoServiceDependency,
    WorkflowExecutionErrorServiceDependency,
    WorkflowExecutionHistoryServiceDependency,
    WorkflowExecutionMetricServiceDependency,
    WorkflowExecutionServiceDependency,
    WorkflowQueueServiceDependency,
    WorkflowRuntimeServiceDependency,
    WorkflowServiceDependency,
    WorkflowStepServiceDependency,
    WorkflowValidationServiceDependency,
)
from apps.api.domain.schemas import (
    JobCreate,
    JobResponse,
    JobStatusResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    VideoCreate,
    VideoResponse,
    WorkflowCreate,
    WorkflowEnqueueResponse,
    WorkflowExecutionErrorResponse,
    WorkflowExecutionHistoryResponse,
    WorkflowExecutionMetricResponse,
    WorkflowExecutionResponse,
    WorkflowResponse,
    WorkflowStepResponse,
    WorkflowValidationResult,
)
from apps.api.errors.exceptions import ApplicationError

router = APIRouter(tags=["domain"])


# --- Projects ---


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate, service: ProjectServiceDependency
) -> ProjectResponse:
    """Create a new video production project."""
    project = await service.create(project_in)
    return ProjectResponse.model_validate(project)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: UUID, service: ProjectServiceDependency) -> ProjectResponse:
    """Retrieve a project by ID."""
    project = await service.get_by_id(project_id)
    if not project:
        raise ApplicationError(
            code="PROJECT_NOT_FOUND",
            message="Project not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return ProjectResponse.model_validate(project)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID, project_in: ProjectUpdate, service: ProjectServiceDependency
) -> ProjectResponse:
    """Update an existing project."""
    project = await service.update(project_id, project_in)
    if not project:
        raise ApplicationError(
            code="PROJECT_NOT_FOUND",
            message="Project not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return ProjectResponse.model_validate(project)


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(service: ProjectServiceDependency) -> list[ProjectResponse]:
    """List all projects."""
    projects = await service.list()
    return [ProjectResponse.model_validate(p) for p in projects]


# --- Videos ---


@router.post("/videos", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def create_video(video_in: VideoCreate, service: VideoServiceDependency) -> VideoResponse:
    """Create a new video entity linked to a project."""
    video = await service.create(video_in)
    return VideoResponse.model_validate(video)


@router.get("/videos/{video_id}", response_model=VideoResponse)
async def get_video(video_id: UUID, service: VideoServiceDependency) -> VideoResponse:
    """Retrieve a video by ID."""
    video = await service.get_by_id(video_id)
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
    workflow_in: WorkflowCreate, service: WorkflowServiceDependency
) -> WorkflowResponse:
    """Create a new workflow configuration for a project."""
    workflow = await service.create(workflow_in)
    return WorkflowResponse.model_validate(workflow)


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: UUID, service: WorkflowServiceDependency) -> WorkflowResponse:
    """Retrieve a workflow by ID."""
    workflow = await service.get_by_id(workflow_id)
    if not workflow:
        raise ApplicationError(
            code="WORKFLOW_NOT_FOUND",
            message="Workflow not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return WorkflowResponse.model_validate(workflow)


@router.post("/workflows/{workflow_id}/validate", response_model=WorkflowValidationResult)
async def validate_workflow(
    workflow_id: UUID, service: WorkflowValidationServiceDependency
) -> WorkflowValidationResult:
    """Validate a workflow definition."""
    return await service.validate_workflow(workflow_id)


@router.post("/workflows/{workflow_id}/run", status_code=status.HTTP_200_OK)
async def run_workflow(
    workflow_id: UUID, service: WorkflowRuntimeServiceDependency
) -> dict[str, Any]:
    """Trigger synchronous execution of a workflow."""
    return await service.execute_workflow(workflow_id)


@router.get("/workflows/{workflow_id}/steps", response_model=list[WorkflowStepResponse])
async def list_workflow_steps(
    workflow_id: UUID, service: WorkflowStepServiceDependency
) -> list[WorkflowStepResponse]:
    """Retrieve all steps for a specific workflow."""
    steps = await service.list_by_workflow(workflow_id)
    return [WorkflowStepResponse.model_validate(s) for s in steps]


# --- Workflow Executions ---


@router.get("/workflow-executions/{execution_id}", response_model=WorkflowExecutionResponse)
async def get_workflow_execution(
    execution_id: UUID, service: WorkflowExecutionServiceDependency
) -> WorkflowExecutionResponse:
    """Retrieve a workflow execution by ID."""
    execution = await service.get_by_id(execution_id)
    if not execution:
        raise ApplicationError(
            code="EXECUTION_NOT_FOUND",
            message="Workflow execution not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return WorkflowExecutionResponse.model_validate(execution)


@router.get(
    "/workflow-executions/{execution_id}/history",
    response_model=list[WorkflowExecutionHistoryResponse],
)
async def list_execution_history(
    execution_id: UUID, service: WorkflowExecutionHistoryServiceDependency
) -> list[WorkflowExecutionHistoryResponse]:
    """Retrieve the audit trail for a specific execution."""
    history = await service.list_by_execution(execution_id)
    return [WorkflowExecutionHistoryResponse.model_validate(h) for h in history]


@router.get(
    "/workflow-executions/{execution_id}/errors",
    response_model=list[WorkflowExecutionErrorResponse],
)
async def list_execution_errors(
    execution_id: UUID, service: WorkflowExecutionErrorServiceDependency
) -> list[WorkflowExecutionErrorResponse]:
    """Retrieve all errors for a specific execution."""
    errors = await service.list_by_execution(execution_id)
    return [WorkflowExecutionErrorResponse.model_validate(e) for e in errors]


@router.get(
    "/workflow-executions/{execution_id}/metrics",
    response_model=list[WorkflowExecutionMetricResponse],
)
async def list_execution_metrics(
    execution_id: UUID, service: WorkflowExecutionMetricServiceDependency
) -> list[WorkflowExecutionMetricResponse]:
    """Retrieve all metrics for a specific execution."""
    metrics = await service.list_by_execution(execution_id)
    return [WorkflowExecutionMetricResponse.model_validate(m) for m in metrics]


@router.post(
    "/workflow-executions/{execution_id}/enqueue",
    response_model=WorkflowEnqueueResponse,
    status_code=status.HTTP_200_OK,
)
async def enqueue_workflow_execution(
    execution_id: UUID, service: WorkflowQueueServiceDependency
) -> WorkflowEnqueueResponse:
    """Dispatch a workflow execution to the async queue."""
    task_id = await service.enqueue_execution(execution_id)
    return WorkflowEnqueueResponse(
        execution_id=execution_id,
        task_id=task_id,
        status="QUEUED",
    )


# --- Jobs ---


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(job_in: JobCreate, service: JobServiceDependency) -> JobResponse:
    """Create a new AI job execution linked to a workflow."""
    job = await service.create(job_in)
    return JobResponse.model_validate(job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID, service: JobServiceDependency) -> JobResponse:
    """Retrieve a job by ID."""
    job = await service.get_by_id(job_id)
    if not job:
        raise ApplicationError(
            code="JOB_NOT_FOUND",
            message="Job not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return JobResponse.model_validate(job)


@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: UUID, service: JobServiceDependency) -> JobStatusResponse:
    """Retrieve the status of a job."""
    status_val = await service.get_status(job_id)
    if not status_val:
        raise ApplicationError(
            code="JOB_NOT_FOUND",
            message="Job not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    from apps.api.domain.models import JobStatus

    return JobStatusResponse(id=job_id, status=JobStatus(status_val))
