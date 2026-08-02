"""Integration tests for the workflow step API."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.application import create_app
from apps.api.config import get_settings
from apps.api.dependencies import get_workflow_step_repository
from apps.api.domain.models import WorkflowStep, WorkflowStepStatus


@pytest.fixture
def mock_step_repository():
    return AsyncMock()


@pytest.mark.asyncio
async def test_list_workflow_steps(mock_step_repository):
    workflow_id = uuid4()
    now = datetime.now(UTC)
    mock_step = WorkflowStep(
        id=uuid4(),
        workflow_id=workflow_id,
        name="Test Step",
        step_type="test",
        order=0,
        config={},
        status=WorkflowStepStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    mock_step_repository.list_by_workflow.return_value = [mock_step]

    app = create_app(get_settings())
    app.dependency_overrides[get_workflow_step_repository] = lambda: mock_step_repository

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/workflows/{workflow_id}/steps")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Step"
    assert data[0]["status"] == "pending"
    mock_step_repository.list_by_workflow.assert_called_once_with(workflow_id)
