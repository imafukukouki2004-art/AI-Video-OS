"""Unit tests for WorkflowArtifact repository and service."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from apps.api.domain.models import WorkflowArtifact
from apps.api.domain.schemas import WorkflowArtifactCreate
from apps.api.repositories.sqlalchemy import WorkflowArtifactRepository
from apps.api.services.domain import WorkflowArtifactService


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def artifact_repo(mock_session):
    return WorkflowArtifactRepository(mock_session)


@pytest.fixture
def artifact_service(artifact_repo):
    return WorkflowArtifactService(artifact_repo)


@pytest.mark.asyncio
async def test_create_artifact(artifact_repo, mock_session):
    execution_id = uuid4()
    step_id = uuid4()
    asset_id = uuid4()
    
    artifact_in = WorkflowArtifactCreate(
        workflow_execution_id=execution_id,
        workflow_step_id=step_id,
        artifact_type="image",
        asset_id=asset_id,
        metadata_data={"width": 1024, "height": 1024}
    )
    
    # Mock session.add and commit
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    
    await artifact_repo.create(artifact_in)
    
    assert mock_session.add.called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_list_by_execution(artifact_repo, mock_session):
    execution_id = uuid4()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        WorkflowArtifact(workflow_execution_id=execution_id, artifact_type="image")
    ]
    mock_session.execute = AsyncMock(return_value=mock_result)
    
    artifacts = await artifact_repo.list_by_execution(execution_id)
    
    assert len(artifacts) == 1
    assert artifacts[0].workflow_execution_id == execution_id


@pytest.mark.asyncio
async def test_service_list_by_execution(artifact_service, artifact_repo):
    execution_id = uuid4()
    artifact_repo.list_by_execution = AsyncMock(return_value=[
        WorkflowArtifact(workflow_execution_id=execution_id, artifact_type="video")
    ])
    
    artifacts = await artifact_service.list_by_execution(execution_id)
    
    assert len(artifacts) == 1
    artifact_repo.list_by_execution.assert_called_once_with(execution_id)
