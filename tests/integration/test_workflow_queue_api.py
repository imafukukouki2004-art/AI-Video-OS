import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, Mock, patch
from datetime import UTC, datetime
from fastapi import FastAPI
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.application import create_app
from apps.api.config import Settings
from apps.api.dependencies import get_database_session

@pytest.fixture
def session() -> AsyncSession:
    session = AsyncMock(spec=AsyncSession)
    def mock_add(obj):
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = uuid4()
        if not hasattr(obj, "created_at") or obj.created_at is None:
            obj.created_at = datetime.now(UTC)
    session.add = Mock(side_effect=mock_add)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session

@pytest.fixture
def app(session) -> FastAPI:
    app = create_app(
        Settings(
            app_env="test",
            log_level="CRITICAL",
            _env_file=None,
        )
    )
    async def provide_session() -> AsyncIterator:
        yield session
    app.dependency_overrides[get_database_session] = provide_session
    return app

@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_enqueue_workflow_execution_api(client: AsyncClient, session: AsyncMock):
    execution_id = uuid4()
    
    mock_task = Mock()
    mock_task.id = "task-123"
    
    # Setup mock for WorkflowExecutionRepository.get_by_id
    from apps.api.domain.models import WorkflowExecution
    mock_execution = WorkflowExecution(id=execution_id, workflow_id=uuid4())
    
    result = Mock()
    result.scalar_one_or_none.return_value = mock_execution
    session.execute.return_value = result
    
    with patch("apps.api.services.workflow_queue.celery_app.send_task", return_value=mock_task):
        response = await client.post(f"/workflow-executions/{execution_id}/enqueue")
        assert response.status_code == 200
        data = response.json()
        assert data["execution_id"] == str(execution_id)
        assert data["task_id"] == "task-123"
        assert data["status"] == "QUEUED"
        
        # Verify that the task_id was updated in the execution
        assert mock_execution.task_id == "task-123"
        assert session.commit.called
