"""Video renderer boundary."""

from typing import Protocol

from apps.api.video_rendering.models import VideoRenderRequest, VideoRenderResult


class VideoRenderingError(RuntimeError):
    """Raised when the rendering backend cannot produce a valid video."""


class VideoRenderer(Protocol):
    """Provider-neutral video rendering interface."""

    async def render(self, request: VideoRenderRequest) -> VideoRenderResult: ...
