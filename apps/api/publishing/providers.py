"""Provider-independent publishing contract and mock implementation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

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

    _providers: ClassVar[dict[str, type[PublishingProvider]]] = {
        "mock": MockPublishingProvider,
    }

    def resolve(self, provider_name: str) -> PublishingProvider:
        provider_type = self._providers.get(provider_name.lower())
        if provider_type is None:
            raise ValueError("Unsupported publishing provider")
        return provider_type()
