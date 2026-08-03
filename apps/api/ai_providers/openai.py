"""OpenAI AI provider implementation."""

from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from apps.api.ai_providers.base import AIImageResponse, AIProvider, AIResponse


class OpenAIProvider(AIProvider):
    """AI provider using OpenAI SDK."""

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate_text(self, prompt: str, **kwargs: Any) -> AIResponse:
        """Generate text using OpenAI Chat Completion."""
        model = kwargs.get("model", self.model)
        system_prompt = kwargs.pop("system_prompt", None)

        messages: list[ChatCompletionMessageParam] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            **{k: v for k, v in kwargs.items() if k not in ["model", "provider"]}
        )
        
        content = response.choices[0].message.content or ""
        
        return AIResponse(
            content=content,
            raw_response=response,
            metadata={
                "provider": "openai",
                "model": model,
                "usage": response.usage.model_dump() if response.usage else {},
            },
        )

    async def generate_image(self, prompt: str, **kwargs: Any) -> AIImageResponse:
        """
        Generate an image using OpenAI DALL-E.
        Note: This is out of scope for TICKET-024 but implemented for interface compliance.
        """
        raise NotImplementedError("Image generation is not supported in TICKET-024")
