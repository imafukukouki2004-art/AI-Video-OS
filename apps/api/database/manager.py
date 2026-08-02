"""Async SQLAlchemy engine, session factory, and connectivity checks."""

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from apps.api.config import Settings
from apps.api.logging import get_logger


class Database:
    """Own the process-wide engine and request-scoped session factory."""

    def __init__(self, settings: Settings) -> None:
        connect_args = {
            "connect_timeout": settings.database_connect_timeout_seconds,
        }
        self.engine: AsyncEngine = create_async_engine(
            settings.database_url.get_secret_value(),
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout_seconds,
            connect_args=connect_args,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async def check_connection(self) -> bool:
        """Return whether PostgreSQL accepts a minimal query without leaking details."""

        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except SQLAlchemyError as error:
            get_logger().warning(
                "database_connection_failed",
                error_type=type(error).__name__,
            )
            return False
        return True

    async def dispose(self) -> None:
        """Release pooled database connections during application shutdown."""

        await self.engine.dispose()
