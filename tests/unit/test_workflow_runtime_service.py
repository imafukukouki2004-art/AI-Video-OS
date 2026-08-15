"""Application-level Workflow completion trigger tests."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from apps.api.domain.models import Workflow
from apps.api.publishing.automatic import AutomaticPublishingCoordinator
from apps.api.services.workflow_runtime import WorkflowRuntimeService


def make_service(workflow: Workflow):
    workflow_repository = AsyncMock()
    workflow_repository.get_by_id.return_value = workflow
    automatic_publishing = AsyncMock(spec=AutomaticPublishingCoordinator)
    dependencies = [AsyncMock() for _ in range(10)]
    service = WorkflowRuntimeService(
        workflow_repository,
        *dependencies,
        automatic_publishing=automatic_publishing,
    )
    service.runtime = AsyncMock()
    return service, automatic_publishing


@pytest.mark.asyncio
async def test_service_triggers_automatic_publishing_only_after_completion() -> None:
    workflow = Workflow(id=uuid4(), workflow_type="video")
    service, automatic_publishing = make_service(workflow)
    execution_id = uuid4()
    service.runtime.run.return_value = {
        "status": "completed",
        "execution_id": execution_id,
    }

    result = await service.execute_workflow(workflow.id)

    assert result["status"] == "completed"
    automatic_publishing.handle_completion.assert_awaited_once_with(workflow, execution_id)

    automatic_publishing.reset_mock()
    service.runtime.run.return_value = {"status": "failed", "execution_id": uuid4()}

    result = await service.execute_workflow(workflow.id)

    assert result["status"] == "failed"
    automatic_publishing.handle_completion.assert_not_awaited()
