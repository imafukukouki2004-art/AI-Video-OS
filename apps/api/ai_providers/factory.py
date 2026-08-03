"""Factory for creating AI provider instances."""

from typing import Any, ClassVar

from apps.api.ai_providers.base import AIProvider
from apps.api.ai_providers.mock import MockAIProvider


class AIProviderFactory:
    """Factory to instantiate AI providers by name."""

    _providers: ClassVar[dict[str, type[AIProvider]]] = {
        "mock": MockAIProvider,
    }

    @classmethod
    def create(cls, provider_name: str, **kwargs: Any) -> AIProvider:
        """Create a provider instance by name."""
        provider_cls = cls._providers.get(provider_name.lower())
        if not provider_cls:
            raise ValueError(f"Unsupported AI provider: {provider_name}")
        
        return provider_cls(**kwargs)
