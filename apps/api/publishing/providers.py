"""Provider-independent publishing contract and mock implementation."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from apps.api.assets.models import Asset


@dataclass(frozen=True)
class PublishingResponse:
    """Normalized successful response returned by publishing providers."""

    external_id: str
    external_url: str
    metadata: dict[str, Any] = field(default_factory=dict)


class PublishingProvider(ABC):
    """Contract implemented by future social publishing adapters."""

    @abstractmethod
    async def publish(
        self,
        asset: Asset,
        *,
        title: str,
        description: str | None,
    ) -> PublishingResponse:
        """Publish an existing asset and return provider-neutral identifiers."""


class PublishingProviderError(Exception):
    """Provider failure with a stable code and safe public message."""

    def __init__(self, code: str, safe_message: str) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


class MockPublishingProvider(PublishingProvider):
    """Deterministic provider used without external API communication."""

    async def publish(
        self,
        asset: Asset,
        *,
        title: str,
        description: str | None,
    ) -> PublishingResponse:
        return PublishingResponse(
            external_id=f"mock-{asset.id}",
            external_url=f"https://example.invalid/publications/{asset.id}",
            metadata={"provider": "mock", "title": title},
        )


class PublishingProviderResolver:
    """Resolve configured provider names without exposing credentials to publications."""

    def __init__(self, providers: Mapping[str, PublishingProvider] | None = None) -> None:
        self._providers: dict[str, PublishingProvider] = {"mock": MockPublishingProvider()}
        if providers:
            self._providers.update({name.lower(): provider for name, provider in providers.items()})

    def resolve(self, provider_name: str) -> PublishingProvider:
        provider = self._providers.get(provider_name.lower())
        if provider is None:
            raise ValueError("Unsupported publishing provider")
        return provider
