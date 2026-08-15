"""Mock-provider E2E contract for queue to publishing completion."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from apps.api.assets.models import Asset
from apps.api.domain.models import (
    Workflow,
    WorkflowArtifact,
    WorkflowExecution,
    WorkflowExecutionStatus,
)
from apps.api.publishing.automatic import AutomaticPublishingCoordinator
from apps.api.publishing.models import Publication, PublicationStatus
from apps.api.publishing.providers import (
    PublishingProvider,
    PublishingProviderResolver,
    PublishingResponse,
)
from apps.api.publishing.queue import PublishingQueueService
from apps.api.publishing.repository import PublicationRepository
from apps.api.publishing.service import PublishingService
from apps.api.repositories import (
    AssetRepository,
    WorkflowArtifactRepository,
    WorkflowExecutionRepository,
)
from apps.worker.tasks import _run_publication


class CountingProvider(PublishingProvider):
    def __init__(self) -> None:
        self.calls = 0

    async def publish(
        self,
        asset: Asset,
        *,
        title: str,
        description: str | None,
    ) -> PublishingResponse:
        self.calls += 1
        return PublishingResponse(
            external_id="queued-video-1",
            external_url="https://example.invalid/queued-video-1",
            metadata={"provider": "mock"},
        )


class FailingProvider(PublishingProvider):
    async def publish(
        self,
        asset: Asset,
        *,
        title: str,
        description: str | None,
    ) -> PublishingResponse:
        raise RuntimeError("provider credential must stay private")


@pytest.mark.asyncio
async def test_publication_enqueue_worker_service_provider_e2e() -> None:
    now = datetime.now(UTC)
    asset = Asset(
        id=uuid4(),
        object_key="assets/runtime/final.mp4",
        filename="final.mp4",
        content_type="video/mp4",
        size_bytes=5,
        created_at=now,
    )
    publication = Publication(
        id=uuid4(),
        asset_id=asset.id,
        provider="mock",
        status=PublicationStatus.PENDING,
        title="Runtime MVP",
        description="Queued publication",
        provider_metadata={},
        created_at=now,
        updated_at=now,
    )
    repository = AsyncMock(spec=PublicationRepository)
    repository.get_by_id.return_value = publication

    async def transition(publication_id, from_status, to_status, update_in):
        if publication.id != publication_id or publication.status is not from_status:
            return None
        publication.status = to_status
        for field, value in update_in.model_dump(exclude_unset=True).items():
            setattr(publication, field, value)
        return publication

    repository.transition_status.side_effect = transition
    task = Mock()

    def send_task(task_name, **kwargs):
        task.id = kwargs["task_id"]
        return task

    queue = PublishingQueueService(repository, task_sender=send_task)
    queued = await queue.enqueue(publication.id)

    assets = AsyncMock(spec=AssetRepository)
    assets.get_by_id.return_value = asset
    provider = CountingProvider()
    publishing = PublishingService(
        repository,
        assets,
        PublishingProviderResolver({"mock": provider}),
    )
    result = await _run_publication(publishing, publication.id)
    duplicate = await _run_publication(publishing, publication.id)

    assert queued.status in {PublicationStatus.QUEUED, PublicationStatus.PUBLISHED}
    assert result == {"status": "published", "publication_id": str(publication.id)}
    assert duplicate == result
    assert publication.status is PublicationStatus.PUBLISHED
    assert publication.external_id == "queued-video-1"
    assert publication.task_id == task.id
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_automatic_publication_provider_failure_keeps_workflow_completed() -> None:
    now = datetime.now(UTC)
    workflow = Workflow(
        id=uuid4(),
        workflow_type="video",
        config={"auto_publish": True, "provider": "mock"},
    )
    execution = WorkflowExecution(
        id=uuid4(),
        workflow_id=workflow.id,
        status=WorkflowExecutionStatus.COMPLETED,
    )
    asset = Asset(
        id=uuid4(),
        object_key="assets/runtime/final.mp4",
        filename="final.mp4",
        content_type="video/mp4",
        size_bytes=5,
        created_at=now,
    )
    artifact = WorkflowArtifact(
        id=uuid4(),
        workflow_execution_id=execution.id,
        artifact_type="video",
        asset_id=asset.id,
        created_at=now,
    )
    publication = Publication(
        id=uuid4(),
        workflow_execution_id=execution.id,
        asset_id=asset.id,
        provider="mock",
        status=PublicationStatus.PENDING,
        title=f"Workflow {workflow.id} video",
        created_at=now,
        updated_at=now,
    )
    executions = AsyncMock(spec=WorkflowExecutionRepository)
    executions.get_by_id.return_value = execution
    artifacts = AsyncMock(spec=WorkflowArtifactRepository)
    artifacts.list_by_execution.return_value = [artifact]
    repository = AsyncMock(spec=PublicationRepository)
    repository.create_automatic.return_value = (publication, True)
    repository.get_by_id.return_value = publication

    async def transition(publication_id, from_status, to_status, update_in):
        if publication.id != publication_id or publication.status is not from_status:
            return None
        publication.status = to_status
        for field, value in update_in.model_dump(exclude_unset=True).items():
            setattr(publication, field, value)
        return publication

    repository.transition_status.side_effect = transition
    assets = AsyncMock(spec=AssetRepository)
    assets.get_by_id.return_value = asset
    success_service = PublishingService(
        repository,
        assets,
        PublishingProviderResolver(),
    )
    task = Mock()

    def send_task(task_name, **kwargs):
        task.id = kwargs["task_id"]
        return task

    coordinator = AutomaticPublishingCoordinator(
        executions,
        artifacts,
        repository,
        success_service,
        PublishingQueueService(repository, task_sender=send_task),
    )

    queued = await coordinator.handle_completion(workflow, execution.id)

    failing_service = PublishingService(
        repository,
        assets,
        PublishingProviderResolver({"mock": FailingProvider()}),
    )
    result = await _run_publication(failing_service, publication.id)

    assert queued.publication is publication
    assert result == {"status": "failed", "error": "PUBLISHING_PROVIDER_ERROR"}
    assert publication.status is PublicationStatus.FAILED
    assert publication.error_code == "PUBLISHING_PROVIDER_ERROR"
    assert execution.status is WorkflowExecutionStatus.COMPLETED
