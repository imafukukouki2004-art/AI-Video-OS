"""Async Redis client lifecycle and connectivity checks."""

from redis.asyncio import Redis
from redis.exceptions import RedisError

from apps.api.config import Settings
from apps.api.logging import get_logger


class RedisManager:
    """Own the process-wide async Redis connection pool."""

    def __init__(self, settings: Settings) -> None:
        self.client: Redis = Redis.from_url(
            settings.redis_url.get_secret_value(),
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=settings.redis_connect_timeout_seconds,
            socket_timeout=settings.redis_socket_timeout_seconds,
        )

    async def check_connection(self) -> bool:
        """Return whether Redis accepts a PING without exposing connection details."""

        try:
            return bool(await self.client.ping())
        except RedisError as error:
            get_logger().warning(
                "redis_connection_failed",
                error_type=type(error).__name__,
            )
            return False

    async def close(self) -> None:
        """Close Redis connections during application shutdown."""

        await self.client.aclose()
