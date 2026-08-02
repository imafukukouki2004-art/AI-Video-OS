"""Integration tests for the workflow execution API."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from apps.api.application import create_app
from apps.api.dependencies import get_workflow_runtime_service
from apps.api.services.workflow_runtime import WorkflowRuntimeService


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_run_workflow_api(app: FastAPI, client: AsyncClient):
    workflow_id = uuid4()

    # Mock the service
    mock_service = AsyncMock(spec=WorkflowRuntimeService)
    mock_service.execute_workflow.return_value = {"status": "completed", "jobs": [str(uuid4())]}

    app.dependency_overrides[get_workflow_runtime_service] = lambda: mock_service

    response = await client.post(f"/workflows/{workflow_id}/run")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    mock_service.execute_workflow.assert_awaited_once_with(workflow_id)

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_run_workflow_not_found(app: FastAPI, client: AsyncClient):
    workflow_id = uuid4()

    from fastapi import status

    from apps.api.errors.exceptions import ApplicationError

    mock_service = AsyncMock(spec=WorkflowRuntimeService)
    mock_service.execute_workflow.side_effect = ApplicationError(
        code="WORKFLOW_NOT_FOUND",
        message="Workflow not found",
        status_code=status.HTTP_404_NOT_FOUND,
    )

    app.dependency_overrides[get_workflow_runtime_service] = lambda: mock_service

    response = await client.post(f"/workflows/{workflow_id}/run")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "WORKFLOW_NOT_FOUND"

    app.dependency_overrides.clear()
