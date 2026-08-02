"""Integration tests for the workflow validation API."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.application import create_app
from apps.api.config import get_settings
from apps.api.dependencies import get_workflow_repository, get_workflow_step_repository
from apps.api.domain.models import Workflow, WorkflowStep


@pytest.fixture
def mock_workflow_repo():
    return AsyncMock()


@pytest.fixture
def mock_step_repo():
    return AsyncMock()


@pytest.mark.asyncio
async def test_validate_workflow_api(mock_workflow_repo, mock_step_repo):
    workflow_id = uuid4()
    mock_workflow = Workflow(id=workflow_id)
    mock_steps = [WorkflowStep(id=uuid4(), name="step1", step_type="test", order=0, config={})]

    mock_workflow_repo.get_by_id.return_value = mock_workflow
    mock_step_repo.list_by_workflow.return_value = mock_steps

    app = create_app(get_settings())
    app.dependency_overrides[get_workflow_repository] = lambda: mock_workflow_repo
    app.dependency_overrides[get_workflow_step_repository] = lambda: mock_step_repo

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(f"/workflows/{workflow_id}/validate")

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["errors"] == []
