"""Pydantic schemas for core domain entities."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.api.domain.models import (
    JobStatus,
    ProjectStatus,
    WorkflowExecutionStatus,
    WorkflowStepStatus,
)


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    status: ProjectStatus = ProjectStatus.DRAFT


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    status: ProjectStatus | None = None


class ProjectResponse(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class VideoBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    asset_id: UUID | None = None


class VideoCreate(VideoBase):
    project_id: UUID


class VideoResponse(VideoBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    created_at: datetime


class WorkflowBase(BaseModel):
    workflow_type: str = Field(..., min_length=1, max_length=100)
    config: dict[str, Any] = Field(default_factory=dict)


class WorkflowCreate(WorkflowBase):
    project_id: UUID


class WorkflowResponse(WorkflowBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    created_at: datetime


class JobBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    status: JobStatus = JobStatus.PENDING
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)


class JobCreate(JobBase):
    workflow_id: UUID
    step_id: UUID | None = None
    execution_id: UUID | None = None


class JobResponse(JobBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: UUID
    step_id: UUID | None
    execution_id: UUID | None
    created_at: datetime


class JobStatusResponse(BaseModel):
    id: UUID
    status: JobStatus


class WorkflowExecutionBase(BaseModel):
    workflow_id: UUID
    status: WorkflowExecutionStatus = WorkflowExecutionStatus.PENDING


class WorkflowExecutionCreate(WorkflowExecutionBase):
    pass


class WorkflowExecutionResponse(WorkflowExecutionBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkflowStepBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    step_type: str = Field(..., min_length=1, max_length=100)
    order: int = Field(..., ge=0)
    config: dict[str, Any] = Field(default_factory=dict)
    status: WorkflowStepStatus = WorkflowStepStatus.PENDING


class WorkflowStepCreate(WorkflowStepBase):
    workflow_id: UUID


class WorkflowStepResponse(WorkflowStepBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: UUID
    created_at: datetime
    updated_at: datetime


class WorkflowExecutionHistoryBase(BaseModel):
    workflow_execution_id: UUID
    workflow_step_id: UUID | None = None
    from_status: str
    to_status: str
    message: str | None = None


class WorkflowExecutionHistoryCreate(WorkflowExecutionHistoryBase):
    pass


class WorkflowExecutionHistoryResponse(WorkflowExecutionHistoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
