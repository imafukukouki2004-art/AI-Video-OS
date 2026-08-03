"""Factory for creating AI provider instances."""

from typing import Any, ClassVar

from apps.api.ai_providers.base import AIProvider
from apps.api.ai_providers.mock import MockAIProvider
from apps.api.ai_providers.openai import OpenAIProvider
from apps.api.config import get_settings


class AIProviderFactory:
    """Factory to instantiate AI providers by name."""

    _providers: ClassVar[dict[str, type[AIProvider]]] = {
        "mock": MockAIProvider,
        "openai": OpenAIProvider,
    }

    @classmethod
    def create(cls, provider_name: str, **kwargs: Any) -> AIProvider:
        """Create a provider instance by name."""
        name = provider_name.lower()
        provider_cls = cls._providers.get(name)
        if not provider_cls:
            raise ValueError(f"Unsupported AI provider: {provider_name}")

        if name == "openai":
            settings = get_settings()
            # Default OpenAI initialization from settings
            # Note: api_key is SecretStr, we need get_secret_value()
            init_kwargs = {
                "api_key": settings.openai_api_key.get_secret_value(),
                "model": settings.openai_model,
            }
            # Allow overriding init args via kwargs if needed
            init_kwargs.update(kwargs)
            return provider_cls(**init_kwargs)

        return provider_cls(**kwargs)
