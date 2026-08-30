"""OpenAI AI provider implementation."""

import base64
from typing import Any, Literal, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from apps.api.ai_providers.base import AIImageResponse, AIProvider, AIResponse

ImageQuality = Literal["low", "medium", "high", "auto"]


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
            **{k: v for k, v in kwargs.items() if k not in ["model", "provider"]},
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
        """Generate an image using the OpenAI Image API."""
        model = kwargs.get("model", "gpt-image-2")
        size = kwargs.get("size", "1024x1024")
        requested_quality = kwargs.get("quality", "auto")
        quality = cast(
            ImageQuality,
            "auto" if requested_quality == "standard" else requested_quality,
        )
        background = kwargs.get("background")

        # If background is provided, append it to the prompt
        if background:
            prompt = f"{prompt}. Background: {background}"

        response = await self.client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
            **{
                k: v
                for k, v in kwargs.items()
                if k
                not in [
                    "model",
                    "provider",
                    "size",
                    "quality",
                    "response_format",
                    "background",
                ]
            },
        )

        if not response.data:
            raise ValueError("OpenAI Image API returned no image data")
        image_data = response.data[0]
        image_url = image_data.url
        image_bytes = base64.b64decode(image_data.b64_json) if image_data.b64_json else None

        return AIImageResponse(
            image_url=image_url,
            image_bytes=image_bytes,
            raw_response=response,
            metadata={
                "provider": "openai",
                "model": model,
                "revised_prompt": image_data.revised_prompt,
            },
        )
