"""Mock AI provider implementation for testing and development."""

from typing import Any

from apps.api.ai_providers.base import AIImageResponse, AIProvider, AIResponse


class MockAIProvider(AIProvider):
    """A mock AI provider that returns static responses."""

    async def generate_text(self, prompt: str, **kwargs: Any) -> AIResponse:
        """Return a static text response."""
        metadata = {"provider": "mock", "model": "mock-text-v1"}
        if "system_prompt" in kwargs:
            metadata["system_prompt"] = kwargs["system_prompt"]

        return AIResponse(
            content=f"Mock response for: {prompt}",
            metadata=metadata,
        )

    async def generate_image(self, prompt: str, **kwargs: Any) -> AIImageResponse:
        """Return a static image response."""
        return AIImageResponse(
            image_url="https://example.com/mock-image.png",
            metadata={"provider": "mock", "model": "mock-image-v1"},
        )
