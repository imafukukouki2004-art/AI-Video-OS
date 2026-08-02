"""FastAPI dependency providers."""

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.cache import RedisManager
from apps.api.config import Settings, get_settings
from apps.api.database import Database
from apps.api.repositories import (
    JobRepository,
    ProjectRepository,
    VideoRepository,
    WorkflowRepository,
)
from apps.api.services import (
    JobService,
    ProjectService,
    VideoService,
    WorkflowService,
)
from apps.api.storage import ObjectStorage

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


def get_storage(request: Request) -> ObjectStorage:
    """Return the application-owned object storage adapter."""

    return cast(ObjectStorage, request.app.state.storage)


StorageDependency = Annotated[ObjectStorage, Depends(get_storage)]


def get_project_repository(session: DatabaseSessionDependency) -> ProjectRepository:
    return ProjectRepository(session)


ProjectRepositoryDependency = Annotated[ProjectRepository, Depends(get_project_repository)]


def get_video_repository(session: DatabaseSessionDependency) -> VideoRepository:
    return VideoRepository(session)


VideoRepositoryDependency = Annotated[VideoRepository, Depends(get_video_repository)]


def get_workflow_repository(session: DatabaseSessionDependency) -> WorkflowRepository:
    return WorkflowRepository(session)


WorkflowRepositoryDependency = Annotated[WorkflowRepository, Depends(get_workflow_repository)]


def get_job_repository(session: DatabaseSessionDependency) -> JobRepository:
    return JobRepository(session)


JobRepositoryDependency = Annotated[JobRepository, Depends(get_job_repository)]


def get_project_service(repo: ProjectRepositoryDependency) -> ProjectService:
    return ProjectService(repo)


ProjectServiceDependency = Annotated[ProjectService, Depends(get_project_service)]


def get_video_service(repo: VideoRepositoryDependency) -> VideoService:
    return VideoService(repo)


VideoServiceDependency = Annotated[VideoService, Depends(get_video_service)]


def get_workflow_service(repo: WorkflowRepositoryDependency) -> WorkflowService:
    return WorkflowService(repo)


WorkflowServiceDependency = Annotated[WorkflowService, Depends(get_workflow_service)]


def get_job_service(repo: JobRepositoryDependency) -> JobService:
    return JobService(repo)


JobServiceDependency = Annotated[JobService, Depends(get_job_service)]
