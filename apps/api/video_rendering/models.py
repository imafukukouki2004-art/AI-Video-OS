"""Typed contracts for video rendering operations."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VideoRenderRequest(BaseModel):
    """Validated single-image request for the rendering foundation."""

    model_config = ConfigDict(frozen=True)

    image_data: bytes = Field(min_length=1)
    image_content_type: str
    duration_seconds: float = Field(default=3.0, gt=0, le=60)
    fps: int = Field(default=30, ge=1, le=60)
    width: int = Field(default=1280, ge=2, le=3840)
    height: int = Field(default=720, ge=2, le=2160)

    @field_validator("image_content_type")
    @classmethod
    def validate_image_content_type(cls, value: str) -> str:
        if not value.startswith("image/"):
            raise ValueError("Video render input must be an image")
        return value

    @field_validator("width", "height")
    @classmethod
    def validate_even_dimension(cls, value: int) -> int:
        if value % 2:
            raise ValueError("Video dimensions must be even")
        return value


class VideoRenderResult(BaseModel):
    """Rendered MP4 bytes and provider-neutral metadata."""

    model_config = ConfigDict(frozen=True)

    video_data: bytes = Field(min_length=1)
    content_type: str = "video/mp4"
    file_extension: str = ".mp4"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, value: str) -> str:
        if value != "video/mp4":
            raise ValueError("Video renderer must return video/mp4")
        return value
