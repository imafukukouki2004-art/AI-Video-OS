"""Post-runtime automatic publishing orchestration."""

from dataclasses import dataclass
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from apps.api.domain.models import Workflow, WorkflowExecutionStatus
from apps.api.errors.exceptions import ApplicationError
from apps.api.logging import get_logger
from apps.api.publishing.models import Publication, PublicationStatus
from apps.api.publishing.queue import PublishingQueueService
from apps.api.publishing.repository import PublicationRepository
from apps.api.publishing.schemas import AutomaticPublicationCreate
from apps.api.publishing.service import PublishingService
from apps.api.repositories import WorkflowArtifactRepository, WorkflowExecutionRepository

logger = get_logger()


class AutomaticPublishingConfig(BaseModel):
    """Minimal opt-in publishing configuration stored in Workflow.config."""

    model_config = ConfigDict(extra="ignore")

    auto_publish: bool = False
    provider: str | None = Field(None, min_length=1, max_length=100)
    publication_title: str | None = Field(None, min_length=1, max_length=255)
    publication_description: str | None = Field(None, max_length=5000)

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str | None) -> str | None:
        return value.strip().lower() if value is not None else None

    @model_validator(mode="after")
    def require_provider_when_enabled(self) -> "AutomaticPublishingConfig":
        if self.auto_publish and not self.provider:
            raise ValueError("provider is required when auto_publish is enabled")
        return self


@dataclass(frozen=True)
class AutomaticPublishingResult:
    """Safe orchestration result for logging and tests."""

    publication: Publication | None = None
    error_code: str | None = None


class AutomaticPublishingCoordinator:
    """Connect a completed workflow to Publishing without changing Runtime responsibility."""

    def __init__(
        self,
        execution_repository: WorkflowExecutionRepository,
        artifact_repository: WorkflowArtifactRepository,
        publication_repository: PublicationRepository,
        publishing_service: PublishingService,
        queue_service: PublishingQueueService,
    ) -> None:
        self.execution_repository = execution_repository
        self.artifact_repository = artifact_repository
        self.publication_repository = publication_repository
        self.publishing_service = publishing_service
        self.queue_service = queue_service

    async def handle_completion(
        self,
        workflow: Workflow,
        execution_id: UUID,
    ) -> AutomaticPublishingResult:
        """Create and queue one publication after durable workflow completion."""

        try:
            config = AutomaticPublishingConfig.model_validate(workflow.config or {})
        except ValidationError:
            return self._failure("INVALID_AUTO_PUBLISH_CONFIG", workflow.id, execution_id)
        if not config.auto_publish:
            return AutomaticPublishingResult()

        try:
            return await self._handle_enabled(workflow, execution_id, config)
        except ApplicationError as error:
            return self._failure(error.code, workflow.id, execution_id)
        except Exception:
            return self._failure("AUTO_PUBLISHING_ERROR", workflow.id, execution_id)

    async def _handle_enabled(
        self,
        workflow: Workflow,
        execution_id: UUID,
        config: AutomaticPublishingConfig,
    ) -> AutomaticPublishingResult:
        """Run the enabled trigger inside the coordinator's failure boundary."""

        execution = await self.execution_repository.get_by_id(execution_id)
        if execution is None or execution.status is not WorkflowExecutionStatus.COMPLETED:
            return AutomaticPublishingResult()

        artifacts = await self.artifact_repository.list_by_execution(execution_id)
        final_video = next(
            (
                artifact
                for artifact in reversed(artifacts)
                if artifact.artifact_type == "video" and artifact.asset_id is not None
            ),
            None,
        )
        if final_video is None:
            return self._failure("FINAL_VIDEO_NOT_FOUND", workflow.id, execution_id)

        provider = config.provider or ""
        title = config.publication_title or f"Workflow {workflow.id} video"
        publication_in = AutomaticPublicationCreate(
            workflow_execution_id=execution_id,
            asset_id=final_video.asset_id,
            provider=provider,
            title=title,
            description=config.publication_description,
        )
        publication, _created = await self.publishing_service.create_automatic(publication_in)
        if publication.status is PublicationStatus.PENDING:
            try:
                publication = await self.queue_service.enqueue(publication.id)
            except ApplicationError as error:
                current = await self.publication_repository.get_by_id(publication.id)
                if current is None or current.status is PublicationStatus.PENDING:
                    return self._failure(error.code, workflow.id, execution_id)
                return self._failure(
                    error.code,
                    workflow.id,
                    execution_id,
                    publication=current,
                )

        logger.info(
            "automatic_publication_ready",
            workflow_id=str(workflow.id),
            execution_id=str(execution_id),
            publication_id=str(publication.id),
            provider=provider,
            publication_status=publication.status.value,
        )
        return AutomaticPublishingResult(publication=publication)

    @staticmethod
    def _failure(
        error_code: str,
        workflow_id: UUID,
        execution_id: UUID,
        *,
        publication: Publication | None = None,
    ) -> AutomaticPublishingResult:
        logger.warning(
            "automatic_publishing_trigger_failed",
            workflow_id=str(workflow_id),
            execution_id=str(execution_id),
            error_code=error_code,
        )
        return AutomaticPublishingResult(publication=publication, error_code=error_code)
