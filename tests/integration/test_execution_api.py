"""Integration tests for the workflow execution tracking API."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from apps.api.application import create_app
from apps.api.dependencies import get_workflow_artifact_service, get_workflow_execution_service
from apps.api.domain.models import WorkflowArtifact, WorkflowExecutionStatus
from apps.api.services.domain import WorkflowArtifactService, WorkflowExecutionService


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_get_workflow_execution_api(app: FastAPI, client: AsyncClient):
    execution_id = uuid4()
    workflow_id = uuid4()

    mock_service = AsyncMock(spec=WorkflowExecutionService)
    from apps.api.domain.models import WorkflowExecution

    mock_execution = WorkflowExecution(
        id=execution_id,
        workflow_id=workflow_id,
        status=WorkflowExecutionStatus.COMPLETED,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    mock_service.get_by_id.return_value = mock_execution

    app.dependency_overrides[get_workflow_execution_service] = lambda: mock_service

    response = await client.get(f"/workflow-executions/{execution_id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(execution_id)
    assert response.json()["status"] == "completed"
    mock_service.get_by_id.assert_awaited_once_with(execution_id)

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_workflow_execution_artifacts_api(app: FastAPI, client: AsyncClient):
    execution_id, step_id, image_asset_id, video_asset_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    image_artifact = WorkflowArtifact(
        id=uuid4(),
        workflow_execution_id=execution_id,
        workflow_step_id=step_id,
        artifact_type="image",
        asset_id=image_asset_id,
        metadata_data={},
        created_at=datetime.now(UTC),
    )
    video_artifact = WorkflowArtifact(
        id=uuid4(),
        workflow_execution_id=execution_id,
        workflow_step_id=step_id,
        artifact_type="video",
        asset_id=video_asset_id,
        metadata_data={"video_codec": "h264"},
        created_at=datetime.now(UTC),
    )
    mock_service = AsyncMock(spec=WorkflowArtifactService)
    mock_service.list_by_execution.return_value = [image_artifact, video_artifact]
    app.dependency_overrides[get_workflow_artifact_service] = lambda: mock_service

    response = await client.get(f"/workflow-executions/{execution_id}/artifacts")

    assert response.status_code == 200
    assert [artifact["artifact_type"] for artifact in response.json()] == ["image", "video"]
    assert response.json()[-1]["asset_id"] == str(video_asset_id)
    mock_service.list_by_execution.assert_awaited_once_with(execution_id)

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_workflow_execution_not_found(app: FastAPI, client: AsyncClient):
    execution_id = uuid4()

    mock_service = AsyncMock(spec=WorkflowExecutionService)
    mock_service.get_by_id.return_value = None

    app.dependency_overrides[get_workflow_execution_service] = lambda: mock_service

    response = await client.get(f"/workflow-executions/{execution_id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EXECUTION_NOT_FOUND"

    app.dependency_overrides.clear()
