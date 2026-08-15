"""Automatic workflow-to-publishing coordinator tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.domain.models import (
    Workflow,
    WorkflowArtifact,
    WorkflowExecution,
    WorkflowExecutionStatus,
)
from apps.api.errors.exceptions import ApplicationError
from apps.api.publishing.automatic import (
    AutomaticPublishingConfig,
    AutomaticPublishingCoordinator,
)
from apps.api.publishing.models import Publication, PublicationStatus
from apps.api.publishing.queue import PublishingQueueService
from apps.api.publishing.repository import PublicationRepository
from apps.api.publishing.schemas import AutomaticPublicationCreate
from apps.api.publishing.service import PublishingService
from apps.api.repositories import (
    WorkflowArtifactRepository,
    WorkflowExecutionRepository,
)

NOW = datetime(2026, 8, 14, tzinfo=UTC)


def make_coordinator():
    executions = AsyncMock(spec=WorkflowExecutionRepository)
    artifacts = AsyncMock(spec=WorkflowArtifactRepository)
    publications = AsyncMock(spec=PublicationRepository)
    publishing = AsyncMock(spec=PublishingService)
    queue = AsyncMock(spec=PublishingQueueService)
    return (
        AutomaticPublishingCoordinator(
            executions,
            artifacts,
            publications,
            publishing,
            queue,
        ),
        executions,
        artifacts,
        publications,
        publishing,
        queue,
    )


def test_automatic_publishing_config_defaults_off_and_requires_provider() -> None:
    assert AutomaticPublishingConfig().auto_publish is False
    with pytest.raises(ValidationError, match="provider is required"):
        AutomaticPublishingConfig(auto_publish=True)
    enabled = AutomaticPublishingConfig(auto_publish=True, provider=" YouTube ")
    assert enabled.provider == "youtube"


@pytest.mark.asyncio
async def test_repository_create_automatic_inserts_or_recovers_duplicate() -> None:
    session = AsyncMock(spec=AsyncSession)
    repository = PublicationRepository(session)
    execution_id, asset_id = uuid4(), uuid4()
    publication_in = AutomaticPublicationCreate(
        workflow_execution_id=execution_id,
        asset_id=asset_id,
        provider="youtube",
        title="Final video",
    )
    publication = Publication(
        id=uuid4(),
        workflow_execution_id=execution_id,
        asset_id=asset_id,
        provider="youtube",
        status=PublicationStatus.PENDING,
        title="Final video",
    )
    inserted = Mock()
    inserted.scalar_one_or_none.return_value = publication
    session.execute.return_value = inserted

    created, was_created = await repository.create_automatic(publication_in)

    assert created is publication
    assert was_created is True
    session.commit.assert_awaited_once()

    conflict = Mock()
    conflict.scalar_one_or_none.return_value = None
    selected = Mock()
    selected.scalar_one_or_none.return_value = publication
    session.execute.side_effect = [conflict, selected]
    session.commit.reset_mock()

    recovered, was_created = await repository.create_automatic(publication_in)

    assert recovered is publication
    assert was_created is False
    session.commit.assert_awaited_once()
    assert "uq_publications_auto_workflow_provider_asset" in {
        constraint.name for constraint in Publication.__table__.constraints
    }


@pytest.mark.asyncio
async def test_auto_publish_off_and_failed_execution_create_nothing() -> None:
    coordinator, executions, artifacts, _, publishing, queue = make_coordinator()
    workflow = Workflow(id=uuid4(), project_id=uuid4(), workflow_type="video", config={})

    disabled = await coordinator.handle_completion(workflow, uuid4())
    assert disabled.publication is None
    executions.get_by_id.assert_not_awaited()

    workflow.config = {"auto_publish": True, "provider": "youtube"}
    executions.get_by_id.return_value = WorkflowExecution(
        id=uuid4(),
        workflow_id=workflow.id,
        status=WorkflowExecutionStatus.FAILED,
    )
    failed = await coordinator.handle_completion(workflow, executions.get_by_id.return_value.id)
    assert failed.publication is None
    artifacts.list_by_execution.assert_not_awaited()
    publishing.create_automatic.assert_not_awaited()
    queue.enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_final_video_is_deterministic_and_queues_one_publication() -> None:
    coordinator, executions, artifacts, _, publishing, queue = make_coordinator()
    execution_id, workflow_id = uuid4(), uuid4()
    first_asset_id, final_asset_id = uuid4(), uuid4()
    workflow = Workflow(
        id=workflow_id,
        project_id=uuid4(),
        workflow_type="video",
        config={
            "auto_publish": True,
            "provider": "youtube",
            "publication_title": "Final video",
        },
    )
    executions.get_by_id.return_value = WorkflowExecution(
        id=execution_id,
        workflow_id=workflow_id,
        status=WorkflowExecutionStatus.COMPLETED,
    )
    artifacts.list_by_execution.return_value = [
        WorkflowArtifact(
            id=uuid4(),
            workflow_execution_id=execution_id,
            artifact_type="video",
            asset_id=first_asset_id,
            created_at=NOW,
        ),
        WorkflowArtifact(
            id=uuid4(),
            workflow_execution_id=execution_id,
            artifact_type="image",
            asset_id=uuid4(),
            created_at=NOW,
        ),
        WorkflowArtifact(
            id=uuid4(),
            workflow_execution_id=execution_id,
            artifact_type="video",
            asset_id=final_asset_id,
            created_at=NOW,
        ),
    ]
    publication = Publication(
        id=uuid4(),
        workflow_execution_id=execution_id,
        asset_id=final_asset_id,
        provider="youtube",
        status=PublicationStatus.PENDING,
        title="Final video",
    )
    queued = Publication(
        id=publication.id,
        workflow_execution_id=execution_id,
        asset_id=final_asset_id,
        provider="youtube",
        status=PublicationStatus.QUEUED,
        title="Final video",
    )
    publishing.create_automatic.return_value = (publication, True)
    queue.enqueue.return_value = queued

    result = await coordinator.handle_completion(workflow, execution_id)

    assert result.publication is queued
    creation = publishing.create_automatic.await_args.args[0]
    assert creation.workflow_execution_id == execution_id
    assert creation.asset_id == final_asset_id
    assert creation.provider == "youtube"
    queue.enqueue.assert_awaited_once_with(publication.id)


@pytest.mark.asyncio
async def test_no_video_and_invalid_provider_fail_without_workflow_mutation() -> None:
    coordinator, executions, artifacts, _, publishing, queue = make_coordinator()
    execution_id, workflow_id = uuid4(), uuid4()
    workflow = Workflow(
        id=workflow_id,
        project_id=uuid4(),
        workflow_type="video",
        config={"auto_publish": True, "provider": "unsupported"},
    )
    execution = WorkflowExecution(
        id=execution_id,
        workflow_id=workflow_id,
        status=WorkflowExecutionStatus.COMPLETED,
    )
    executions.get_by_id.return_value = execution
    artifacts.list_by_execution.return_value = []

    missing = await coordinator.handle_completion(workflow, execution_id)
    assert missing.error_code == "FINAL_VIDEO_NOT_FOUND"
    assert execution.status is WorkflowExecutionStatus.COMPLETED

    video_asset_id = uuid4()
    artifacts.list_by_execution.return_value = [
        WorkflowArtifact(
            id=uuid4(),
            workflow_execution_id=execution_id,
            artifact_type="video",
            asset_id=video_asset_id,
        )
    ]
    publishing.create_automatic.side_effect = Exception("provider secret must not leak")
    invalid = await coordinator.handle_completion(workflow, execution_id)
    assert invalid.error_code == "AUTO_PUBLISHING_ERROR"
    assert execution.status is WorkflowExecutionStatus.COMPLETED
    queue.enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_completion_does_not_reenqueue_terminal_publication() -> None:
    coordinator, executions, artifacts, _, publishing, queue = make_coordinator()
    execution_id, workflow_id, asset_id = uuid4(), uuid4(), uuid4()
    workflow = Workflow(
        id=workflow_id,
        project_id=uuid4(),
        workflow_type="video",
        config={"auto_publish": True, "provider": "youtube"},
    )
    executions.get_by_id.return_value = WorkflowExecution(
        id=execution_id,
        workflow_id=workflow_id,
        status=WorkflowExecutionStatus.COMPLETED,
    )
    artifacts.list_by_execution.return_value = [
        WorkflowArtifact(
            id=uuid4(),
            workflow_execution_id=execution_id,
            artifact_type="video",
            asset_id=asset_id,
        )
    ]
    publication = Publication(
        id=uuid4(),
        workflow_execution_id=execution_id,
        asset_id=asset_id,
        provider="youtube",
        status=PublicationStatus.QUEUED,
        title="Video",
    )
    publishing.create_automatic.return_value = (publication, False)

    first = await coordinator.handle_completion(workflow, execution_id)
    second = await coordinator.handle_completion(workflow, execution_id)

    assert first.publication is publication
    assert second.publication is publication
    assert publishing.create_automatic.await_count == 2
    queue.enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_publishing_failure_isolated_from_completed_workflow() -> None:
    coordinator, executions, artifacts, publications, publishing, queue = make_coordinator()
    execution_id, workflow_id, asset_id = uuid4(), uuid4(), uuid4()
    workflow = Workflow(
        id=workflow_id,
        project_id=uuid4(),
        workflow_type="video",
        config={"auto_publish": True, "provider": "youtube"},
    )
    execution = WorkflowExecution(
        id=execution_id,
        workflow_id=workflow_id,
        status=WorkflowExecutionStatus.COMPLETED,
    )
    executions.get_by_id.return_value = execution
    artifacts.list_by_execution.return_value = [
        WorkflowArtifact(
            id=uuid4(),
            workflow_execution_id=execution_id,
            artifact_type="video",
            asset_id=asset_id,
        )
    ]
    publication = Publication(
        id=uuid4(),
        workflow_execution_id=execution_id,
        asset_id=asset_id,
        provider="youtube",
        status=PublicationStatus.PENDING,
        title="Video",
    )
    failed = Publication(
        id=publication.id,
        workflow_execution_id=execution_id,
        asset_id=asset_id,
        provider="youtube",
        status=PublicationStatus.FAILED,
        title="Video",
        error_code="PUBLISHING_QUEUE_ERROR",
    )
    publishing.create_automatic.return_value = (publication, True)
    queue.enqueue.side_effect = ApplicationError(
        code="PUBLISHING_QUEUE_ERROR",
        message="The publication could not be queued.",
        status_code=503,
    )
    publications.get_by_id.return_value = failed

    result = await coordinator.handle_completion(workflow, execution_id)

    assert result.publication is failed
    assert result.error_code == "PUBLISHING_QUEUE_ERROR"
    assert execution.status is WorkflowExecutionStatus.COMPLETED

    artifacts.list_by_execution.side_effect = RuntimeError("database credential")
    repository_failure = await coordinator.handle_completion(workflow, execution_id)
    assert repository_failure.error_code == "AUTO_PUBLISHING_ERROR"
    assert execution.status is WorkflowExecutionStatus.COMPLETED
