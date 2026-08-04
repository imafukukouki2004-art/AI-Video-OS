"""Public asset API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AssetBase(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=255)
    size_bytes: int = Field(..., ge=0)


class AssetCreate(AssetBase):
    id: UUID | None = None
    object_key: str = Field(..., min_length=1, max_length=512)


class AssetResponse(AssetBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class PresignedUrlResponse(BaseModel):
    url: str
    expires_in: int = Field(gt=0)
