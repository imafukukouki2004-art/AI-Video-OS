"""SQLAlchemy implementations of core domain repositories."""

from collections.abc import Sequence
from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.domain.models import Job, Project, Video, Workflow
from apps.api.domain.schemas import (
    JobCreate,
    ProjectCreate,
    ProjectUpdate,
    VideoCreate,
    WorkflowCreate,
)

T = TypeVar("T")
CreateSchema = TypeVar("CreateSchema")
UpdateSchema = TypeVar("UpdateSchema")


class SQLAlchemyRepository[T, CreateSchema, UpdateSchema]:
    """Base SQLAlchemy repository with common CRUD operations."""

    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self.session = session
        self.model = model

    async def create(self, schema: CreateSchema) -> T:
        if hasattr(schema, "model_dump"):
            data = schema.model_dump()
        else:
            data = dict(schema)  # type: ignore

        instance = self.model(**data)
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def get_by_id(self, id: UUID) -> T | None:
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)  # type: ignore
        )
        return result.scalar_one_or_none()

    async def list(self) -> Sequence[T]:
        result = await self.session.execute(select(self.model))
        return result.scalars().all()

    async def update(self, id: UUID, schema: UpdateSchema) -> T | None:
        instance = await self.get_by_id(id)
        if not instance:
            return None

        if hasattr(schema, "model_dump"):
            update_data = schema.model_dump(exclude_unset=True)
        else:
            update_data = dict(schema)  # type: ignore

        for field, value in update_data.items():
            setattr(instance, field, value)

        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def get_status(self, id: UUID) -> str | None:
        instance = await self.get_by_id(id)
        if not instance:
            return None
        return str(getattr(instance, "status", None))


class ProjectRepository(SQLAlchemyRepository[Project, ProjectCreate, ProjectUpdate]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Project)


class VideoRepository(SQLAlchemyRepository[Video, VideoCreate, Any]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Video)


class WorkflowRepository(SQLAlchemyRepository[Workflow, WorkflowCreate, Any]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Workflow)


class JobRepository(SQLAlchemyRepository[Job, JobCreate, Any]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Job)
