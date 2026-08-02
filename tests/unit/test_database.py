"""Database foundation unit tests."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from apps.api.config import Settings
from apps.api.database import Database


def make_database() -> Database:
    return Database(
        Settings(
            app_env="test",
            database_url="postgresql+psycopg://user:password@database:5432/test_db",
            _env_file=None,
        )
    )


@pytest.mark.asyncio
async def test_database_uses_async_postgresql_driver() -> None:
    database = make_database()

    assert database.engine.url.drivername == "postgresql+psycopg"
    assert database.engine.url.render_as_string(hide_password=True).endswith(
        "user:***@database:5432/test_db"
    )

    await database.dispose()


@pytest.mark.asyncio
async def test_connection_health_check_succeeds() -> None:
    connection = AsyncMock(spec=AsyncConnection)

    @asynccontextmanager
    async def connect() -> AsyncIterator[AsyncConnection]:
        yield connection

    database = make_database()
    engine = Mock(spec=AsyncEngine)
    engine.connect = connect
    database.engine = cast(AsyncEngine, engine)

    assert await database.check_connection() is True
    connection.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_connection_health_check_handles_sqlalchemy_error() -> None:
    @asynccontextmanager
    async def connect() -> AsyncIterator[AsyncConnection]:
        raise OperationalError("SELECT 1", {}, RuntimeError("unavailable"))
        yield AsyncMock(spec=AsyncConnection)  # pragma: no cover

    database = make_database()
    engine = Mock(spec=AsyncEngine)
    engine.connect = connect
    database.engine = cast(AsyncEngine, engine)

    assert await database.check_connection() is False
