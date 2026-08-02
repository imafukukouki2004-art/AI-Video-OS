"""Integration tests for the workflow error API."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.application import create_app
from apps.api.config import get_settings
from apps.api.dependencies import get_workflow_execution_error_repository
from apps.api.domain.models import WorkflowExecutionError


@pytest.fixture
def mock_error_repo():
    return AsyncMock()


@pytest.mark.asyncio
async def test_list_execution_errors_api(mock_error_repo):
    execution_id = uuid4()
    mock_errors = [
        WorkflowExecutionError(
            id=uuid4(),
            workflow_execution_id=execution_id,
            error_code="ERROR_1",
            error_message="Message 1",
            error_type="Type1",
            created_at=datetime.now(UTC),
        )
    ]

    mock_error_repo.list_by_execution.return_value = mock_errors

    app = create_app(get_settings())
    app.dependency_overrides[get_workflow_execution_error_repository] = lambda: mock_error_repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/workflow-executions/{execution_id}/errors")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["error_code"] == "ERROR_1"
    assert "created_at" in data[0]
