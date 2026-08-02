"""Base service class for application services."""

from collections.abc import Sequence
from typing import TypeVar
from uuid import UUID

from apps.api.repositories.base import Repository

T = TypeVar("T")
CreateSchema = TypeVar("CreateSchema")
UpdateSchema = TypeVar("UpdateSchema")


class BaseService[T, CreateSchema, UpdateSchema]:
    """Base application service providing common orchestration logic."""

    def __init__(self, repository: Repository[T, CreateSchema, UpdateSchema]) -> None:
        self.repository = repository

    async def create(self, schema: CreateSchema) -> T:
        """Orchestrate entity creation."""
        return await self.repository.create(schema)

    async def get_by_id(self, id: UUID) -> T | None:
        """Orchestrate entity retrieval by ID."""
        return await self.repository.get_by_id(id)

    async def list(self) -> Sequence[T]:
        """Orchestrate entity listing."""
        return await self.repository.list()

    async def update(self, id: UUID, schema: UpdateSchema) -> T | None:
        """Orchestrate entity update."""
        return await self.repository.update(id, schema)

    async def get_status(self, id: UUID) -> str | None:
        """Orchestrate entity status retrieval."""
        return await self.repository.get_status(id)
