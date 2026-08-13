"""API and repository schemas for publications."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.api.publishing.models import PublicationStatus


class PublicationCreate(BaseModel):
    asset_id: UUID
    provider: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)


class PublicationUpdate(BaseModel):
    status: PublicationStatus | None = None
    external_id: str | None = Field(None, max_length=255)
    external_url: str | None = Field(None, max_length=2048)
    provider_metadata: dict[str, Any] | None = None
    error_code: str | None = Field(None, max_length=100)
    error_message: str | None = Field(None, max_length=1000)
    published_at: datetime | None = None


class PublicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    asset_id: UUID
    provider: str
    status: PublicationStatus
    title: str
    description: str | None
    external_id: str | None
    external_url: str | None
    provider_metadata: dict[str, Any]
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
