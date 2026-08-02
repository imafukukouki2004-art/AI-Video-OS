"""Redis connectivity foundation tests."""

from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError

from apps.api.cache import RedisManager
from apps.api.config import Settings


def make_manager() -> RedisManager:
    return RedisManager(
        Settings(
            app_env="test",
            redis_url="redis://:password@cache:6379/0",
            _env_file=None,
        )
    )


@pytest.mark.asyncio
async def test_redis_manager_uses_configured_url_without_exposing_it() -> None:
    manager = make_manager()

    connection = manager.client.connection_pool.connection_kwargs
    assert connection["host"] == "cache"
    assert connection["db"] == 0
    assert "password" not in repr(manager)

    await manager.close()


@pytest.mark.asyncio
async def test_redis_health_check_succeeds() -> None:
    manager = make_manager()
    client = Mock(spec=Redis)
    client.ping = AsyncMock(return_value=True)
    manager.client = cast(Redis, client)

    assert await manager.check_connection() is True
    client.ping.assert_awaited_once()


@pytest.mark.asyncio
async def test_redis_health_check_handles_connection_error() -> None:
    manager = make_manager()
    client = Mock(spec=Redis)
    client.ping = AsyncMock(side_effect=ConnectionError("unavailable"))
    manager.client = cast(Redis, client)

    assert await manager.check_connection() is False
