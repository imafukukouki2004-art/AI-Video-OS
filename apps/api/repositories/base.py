"""Base repository interfaces and shared types."""

from collections.abc import Sequence
from typing import Protocol, TypeVar
from uuid import UUID

T = TypeVar("T")
CreateSchema = TypeVar("CreateSchema")
UpdateSchema = TypeVar("UpdateSchema")


class Repository[T, CreateSchema, UpdateSchema](Protocol):
    """Generic repository protocol for core domain entities."""

    async def create(self, schema: CreateSchema) -> T:
        """Persist a new entity instance."""
        ...

    async def get_by_id(self, id: UUID) -> T | None:
        """Retrieve an entity by its primary key."""
        ...

    async def list(self) -> Sequence[T]:
        """Retrieve all entity instances."""
        ...

    async def update(self, id: UUID, schema: UpdateSchema) -> T | None:
        """Update an existing entity instance."""
        ...

    async def get_status(self, id: UUID) -> str | None:
        """Retrieve the status of an entity."""
        ...
