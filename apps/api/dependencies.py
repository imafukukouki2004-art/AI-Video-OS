"""FastAPI dependency providers."""

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.cache import RedisManager
from apps.api.config import Settings, get_settings
from apps.api.database import Database

SettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_database(request: Request) -> Database:
    """Return the application-owned database manager."""

    return cast(Database, request.app.state.database)


DatabaseDependency = Annotated[Database, Depends(get_database)]


async def get_database_session(database: DatabaseDependency) -> AsyncIterator[AsyncSession]:
    """Yield one transaction-capable session for the current request."""

    async with database.session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


DatabaseSessionDependency = Annotated[AsyncSession, Depends(get_database_session)]


def get_redis(request: Request) -> RedisManager:
    """Return the application-owned Redis manager."""

    return cast(RedisManager, request.app.state.redis)


RedisDependency = Annotated[RedisManager, Depends(get_redis)]
