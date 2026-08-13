"""Integration tests for the workflow execution API."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from apps.api.application import create_app
from apps.api.dependencies import get_workflow_runtime_service, get_workflow_step_service
from apps.api.domain.models import WorkflowStep, WorkflowStepStatus
from apps.api.services.domain import WorkflowStepService
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
async def test_create_workflow_step_api(app: FastAPI, client: AsyncClient):
    workflow_id, step_id = uuid4(), uuid4()
    step = WorkflowStep(
        id=step_id,
        workflow_id=workflow_id,
        name="GenerateScript",
        step_type="ai",
        order=1,
        config={"provider": "mock", "operation": "text_generation", "prompt": "Write"},
        status=WorkflowStepStatus.PENDING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_service = AsyncMock(spec=WorkflowStepService)
    mock_service.create.return_value = step
    app.dependency_overrides[get_workflow_step_service] = lambda: mock_service
    payload = {
        "workflow_id": str(workflow_id),
        "name": "GenerateScript",
        "step_type": "ai",
        "order": 1,
        "config": {"provider": "mock", "operation": "text_generation", "prompt": "Write"},
    }

    response = await client.post("/workflow-steps", json=payload)

    assert response.status_code == 201
    assert response.json()["id"] == str(step_id)
    assert response.json()["workflow_id"] == str(workflow_id)
    create_input = mock_service.create.await_args.args[0]
    assert create_input.config["operation"] == "text_generation"
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


@pytest.mark.asyncio
async def test_get_job_status_api(app: FastAPI, client: AsyncClient):
    job_id = uuid4()
    from apps.api.dependencies import get_job_service
    from apps.api.services.domain import JobService

    mock_service = AsyncMock(spec=JobService)
    mock_service.get_status.return_value = "running"

    app.dependency_overrides[get_job_service] = lambda: mock_service

    response = await client.get(f"/jobs/{job_id}/status")

    assert response.status_code == 200
    assert response.json()["status"] == "running"
    mock_service.get_status.assert_awaited_once_with(job_id)

    app.dependency_overrides.clear()
