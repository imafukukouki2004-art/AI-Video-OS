"""FastAPI dependency providers."""

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.cache import RedisManager
from apps.api.config import Settings, get_settings
from apps.api.database import Database
from apps.api.repositories import (
    AssetRepository,
    JobRepository,
    ProjectRepository,
    VideoRepository,
    WorkflowArtifactRepository,
    WorkflowExecutionErrorRepository,
    WorkflowExecutionHistoryRepository,
    WorkflowExecutionMetricRepository,
    WorkflowExecutionRepository,
    WorkflowRepository,
    WorkflowStepRepository,
)
from apps.api.services import (
    JobService,
    ProjectService,
    PromptBuilder,
    VideoService,
    WorkflowArtifactService,
    WorkflowExecutionErrorService,
    WorkflowExecutionHistoryService,
    WorkflowExecutionMetricService,
    WorkflowExecutionService,
    WorkflowQueueService,
    WorkflowRuntimeService,
    WorkflowService,
    WorkflowStepService,
    WorkflowValidationService,
)
from apps.api.storage import ObjectStorage
from apps.api.video_rendering import FFmpegVideoRenderer, VideoRenderer

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


def get_prompt_builder() -> PromptBuilder:
    """Return the stateless prompt composition service."""
    return PromptBuilder()


PromptBuilderDependency = Annotated[PromptBuilder, Depends(get_prompt_builder)]


def get_video_renderer() -> VideoRenderer:
    """Return the configured video rendering adapter."""
    return FFmpegVideoRenderer()


VideoRendererDependency = Annotated[VideoRenderer, Depends(get_video_renderer)]


def get_project_repository(session: DatabaseSessionDependency) -> ProjectRepository:
    return ProjectRepository(session)


ProjectRepositoryDependency = Annotated[ProjectRepository, Depends(get_project_repository)]


def get_video_repository(session: DatabaseSessionDependency) -> VideoRepository:
    return VideoRepository(session)


VideoRepositoryDependency = Annotated[VideoRepository, Depends(get_video_repository)]


def get_workflow_repository(session: DatabaseSessionDependency) -> WorkflowRepository:
    return WorkflowRepository(session)


WorkflowRepositoryDependency = Annotated[WorkflowRepository, Depends(get_workflow_repository)]


def get_workflow_step_repository(session: DatabaseSessionDependency) -> WorkflowStepRepository:
    return WorkflowStepRepository(session)


WorkflowStepRepositoryDependency = Annotated[
    WorkflowStepRepository, Depends(get_workflow_step_repository)
]


def get_job_repository(session: DatabaseSessionDependency) -> JobRepository:
    return JobRepository(session)


JobRepositoryDependency = Annotated[JobRepository, Depends(get_job_repository)]


def get_workflow_execution_repository(
    session: DatabaseSessionDependency,
) -> WorkflowExecutionRepository:
    return WorkflowExecutionRepository(session)


WorkflowExecutionRepositoryDependency = Annotated[
    WorkflowExecutionRepository, Depends(get_workflow_execution_repository)
]


def get_workflow_execution_history_repository(
    session: DatabaseSessionDependency,
) -> WorkflowExecutionHistoryRepository:
    return WorkflowExecutionHistoryRepository(session)


WorkflowExecutionHistoryRepositoryDependency = Annotated[
    WorkflowExecutionHistoryRepository, Depends(get_workflow_execution_history_repository)
]


def get_workflow_execution_error_repository(
    session: DatabaseSessionDependency,
) -> WorkflowExecutionErrorRepository:
    return WorkflowExecutionErrorRepository(session)


WorkflowExecutionErrorRepositoryDependency = Annotated[
    WorkflowExecutionErrorRepository, Depends(get_workflow_execution_error_repository)
]


def get_workflow_execution_metric_repository(
    session: DatabaseSessionDependency,
) -> WorkflowExecutionMetricRepository:
    return WorkflowExecutionMetricRepository(session)


WorkflowExecutionMetricRepositoryDependency = Annotated[
    WorkflowExecutionMetricRepository, Depends(get_workflow_execution_metric_repository)
]


def get_workflow_artifact_repository(
    session: DatabaseSessionDependency,
) -> WorkflowArtifactRepository:
    return WorkflowArtifactRepository(session)


WorkflowArtifactRepositoryDependency = Annotated[
    WorkflowArtifactRepository, Depends(get_workflow_artifact_repository)
]


def get_asset_repository(session: DatabaseSessionDependency) -> AssetRepository:
    return AssetRepository(session)


AssetRepositoryDependency = Annotated[AssetRepository, Depends(get_asset_repository)]


def get_project_service(repo: ProjectRepositoryDependency) -> ProjectService:
    return ProjectService(repo)


ProjectServiceDependency = Annotated[ProjectService, Depends(get_project_service)]


def get_video_service(repo: VideoRepositoryDependency) -> VideoService:
    return VideoService(repo)


VideoServiceDependency = Annotated[VideoService, Depends(get_video_service)]


def get_workflow_service(
    repo: WorkflowRepositoryDependency, step_repo: WorkflowStepRepositoryDependency
) -> WorkflowService:
    return WorkflowService(repo, step_repo)


WorkflowServiceDependency = Annotated[WorkflowService, Depends(get_workflow_service)]


def get_workflow_step_service(repo: WorkflowStepRepositoryDependency) -> WorkflowStepService:
    return WorkflowStepService(repo)


WorkflowStepServiceDependency = Annotated[WorkflowStepService, Depends(get_workflow_step_service)]


def get_job_service(repo: JobRepositoryDependency) -> JobService:
    return JobService(repo)


JobServiceDependency = Annotated[JobService, Depends(get_job_service)]


def get_workflow_execution_service(
    repo: WorkflowExecutionRepositoryDependency,
) -> WorkflowExecutionService:
    return WorkflowExecutionService(repo)


WorkflowExecutionServiceDependency = Annotated[
    WorkflowExecutionService, Depends(get_workflow_execution_service)
]


def get_workflow_execution_history_service(
    repo: WorkflowExecutionHistoryRepositoryDependency,
) -> WorkflowExecutionHistoryService:
    return WorkflowExecutionHistoryService(repo)


WorkflowExecutionHistoryServiceDependency = Annotated[
    WorkflowExecutionHistoryService, Depends(get_workflow_execution_history_service)
]


def get_workflow_execution_error_service(
    repo: WorkflowExecutionErrorRepositoryDependency,
) -> WorkflowExecutionErrorService:
    return WorkflowExecutionErrorService(repo)


WorkflowExecutionErrorServiceDependency = Annotated[
    WorkflowExecutionErrorService, Depends(get_workflow_execution_error_service)
]


def get_workflow_execution_metric_service(
    repo: WorkflowExecutionMetricRepositoryDependency,
) -> WorkflowExecutionMetricService:
    return WorkflowExecutionMetricService(repo)


WorkflowExecutionMetricServiceDependency = Annotated[
    WorkflowExecutionMetricService, Depends(get_workflow_execution_metric_service)
]


def get_workflow_artifact_service(
    repo: WorkflowArtifactRepositoryDependency,
) -> WorkflowArtifactService:
    return WorkflowArtifactService(repo)


WorkflowArtifactServiceDependency = Annotated[
    WorkflowArtifactService, Depends(get_workflow_artifact_service)
]


def get_workflow_queue_service(
    repo: WorkflowExecutionRepositoryDependency,
) -> WorkflowQueueService:
    return WorkflowQueueService(repo)


WorkflowQueueServiceDependency = Annotated[
    WorkflowQueueService, Depends(get_workflow_queue_service)
]


def get_workflow_validation_service(
    workflow_repo: WorkflowRepositoryDependency,
    step_repo: WorkflowStepRepositoryDependency,
) -> WorkflowValidationService:
    return WorkflowValidationService(workflow_repo, step_repo)


WorkflowValidationServiceDependency = Annotated[
    WorkflowValidationService, Depends(get_workflow_validation_service)
]


def get_workflow_runtime_service(
    workflow_repo: WorkflowRepositoryDependency,
    job_repo: JobRepositoryDependency,
    execution_repo: WorkflowExecutionRepositoryDependency,
    step_repo: WorkflowStepRepositoryDependency,
    history_repo: WorkflowExecutionHistoryRepositoryDependency,
    error_repo: WorkflowExecutionErrorRepositoryDependency,
    metric_repo: WorkflowExecutionMetricRepositoryDependency,
    artifact_repo: WorkflowArtifactRepositoryDependency,
    asset_repo: AssetRepositoryDependency,
    storage: StorageDependency,
    prompt_builder: PromptBuilderDependency,
    video_renderer: VideoRendererDependency,
) -> WorkflowRuntimeService:
    return WorkflowRuntimeService(
        workflow_repo,
        job_repo,
        execution_repo,
        step_repo,
        history_repo,
        error_repo,
        metric_repo,
        artifact_repo,
        asset_repo,
        storage,
        prompt_builder,
        video_renderer,
    )


WorkflowRuntimeServiceDependency = Annotated[
    WorkflowRuntimeService, Depends(get_workflow_runtime_service)
]
