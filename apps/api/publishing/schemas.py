"""API and repository schemas for publications."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.api.publishing.models import PublicationStatus, PublishingConnectionStatus


class PublicationCreate(BaseModel):
    asset_id: UUID
    provider: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)


class AutomaticPublicationCreate(PublicationCreate):
    """Internal creation contract linking a publication to one workflow execution."""

    workflow_execution_id: UUID


class PublicationUpdate(BaseModel):
    status: PublicationStatus | None = None
    external_id: str | None = Field(None, max_length=255)
    external_url: str | None = Field(None, max_length=2048)
    provider_metadata: dict[str, Any] | None = None
    error_code: str | None = Field(None, max_length=100)
    error_message: str | None = Field(None, max_length=1000)
    published_at: datetime | None = None
    scheduled_at: datetime | None = None
    queued_at: datetime | None = None
    started_at: datetime | None = None
    task_id: str | None = Field(None, max_length=255)


class PublicationSchedule(BaseModel):
    scheduled_at: datetime

    @field_validator("scheduled_at")
    @classmethod
    def require_timezone_and_normalize_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("scheduled_at must include a timezone offset")
        return value.astimezone(UTC)


class PublicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    asset_id: UUID
    workflow_execution_id: UUID | None
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
    scheduled_at: datetime | None
    queued_at: datetime | None
    started_at: datetime | None
    task_id: str | None


class PublishingConnectionCreate(BaseModel):
    provider: str = Field(..., min_length=1, max_length=100)
    status: PublishingConnectionStatus = PublishingConnectionStatus.PENDING
    scopes: list[str] = Field(default_factory=list)


class PublishingConnectionUpdate(BaseModel):
    status: PublishingConnectionStatus | None = None
    scopes: list[str] | None = None
    account_id: str | None = Field(None, max_length=255)
    account_name: str | None = Field(None, max_length=255)
    error_code: str | None = Field(None, max_length=100)
    error_message: str | None = Field(None, max_length=1000)
    connected_at: datetime | None = None
    disconnected_at: datetime | None = None


class PublishingCredentialCreate(BaseModel):
    connection_id: UUID
    encrypted_refresh_token: str = Field(..., min_length=1)


class PublishingCredentialUpdate(BaseModel):
    encrypted_refresh_token: str | None = Field(None, min_length=1)


class PublishingOAuthStateCreate(BaseModel):
    connection_id: UUID
    state_digest: str = Field(..., min_length=64, max_length=64)
    expires_at: datetime


class PublishingOAuthStateUpdate(BaseModel):
    consumed_at: datetime | None = None


class PublishingConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: str
    status: PublishingConnectionStatus
    scopes: list[str]
    account_id: str | None
    account_name: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    connected_at: datetime | None
    disconnected_at: datetime | None


class YouTubeAuthorizationResponse(BaseModel):
    connection_id: UUID
    authorization_url: str
    expires_at: datetime
