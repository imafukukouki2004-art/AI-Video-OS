"""Base interface and models for AI providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AIResponse:
    """Unified response model for AI provider operations."""

    content: str
    raw_response: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AIImageResponse:
    """Unified response model for AI image generation operations."""

    image_url: str
    raw_response: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AIProvider(ABC):
    """Abstract base class for all AI providers."""

    @abstractmethod
    async def generate_text(self, prompt: str, **kwargs: Any) -> AIResponse:
        """Generate text based on a prompt."""
        pass

    @abstractmethod
    async def generate_image(self, prompt: str, **kwargs: Any) -> AIImageResponse:
        """Generate an image based on a prompt."""
        pass
