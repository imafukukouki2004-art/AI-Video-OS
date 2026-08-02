"""Integration tests for the workflow execution history API."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.application import create_app
from apps.api.config import get_settings
from apps.api.dependencies import get_workflow_execution_history_repository
from apps.api.domain.models import WorkflowExecutionHistory


@pytest.fixture
def mock_history_repository():
    return AsyncMock()


@pytest.mark.asyncio
async def test_list_execution_history(mock_history_repository):
    execution_id = uuid4()
    now = datetime.now(UTC)
    mock_history = WorkflowExecutionHistory(
        id=uuid4(),
        workflow_execution_id=execution_id,
        workflow_step_id=None,
        from_status="pending",
        to_status="running",
        message="Started",
        created_at=now,
    )
    mock_history_repository.list_by_execution.return_value = [mock_history]

    app = create_app(get_settings())
    app.dependency_overrides[get_workflow_execution_history_repository] = (
        lambda: mock_history_repository
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/workflow-executions/{execution_id}/history")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["from_status"] == "pending"
    assert data[0]["to_status"] == "running"
    mock_history_repository.list_by_execution.assert_called_once_with(execution_id)
