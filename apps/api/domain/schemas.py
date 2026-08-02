"""Pydantic schemas for core domain entities."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.api.domain.models import JobStatus, ProjectStatus


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


class JobResponse(JobBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: UUID
    created_at: datetime
