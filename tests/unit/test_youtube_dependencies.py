"""Dependency injection tests for publishing provider resolution."""

from unittest.mock import Mock

from apps.api.config import Settings
from apps.api.dependencies import get_publishing_provider_resolver
from apps.api.publishing import MockPublishingProvider, YouTubePublishingProvider
from apps.api.storage import ObjectStorage


def test_dependency_resolver_registers_mock_and_youtube() -> None:
    settings = Settings(
        app_env="test",
        _env_file=None,
    )
    storage = Mock(spec=ObjectStorage)

    resolver = get_publishing_provider_resolver(settings, storage)

    assert isinstance(resolver.resolve("mock"), MockPublishingProvider)
    assert isinstance(resolver.resolve("youtube"), YouTubePublishingProvider)
