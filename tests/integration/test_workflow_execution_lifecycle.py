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
from apps.api.domain.models import WorkflowExecution, Workflow

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
async def test_enqueue_workflow_lifecycle_api(client: AsyncClient, session: AsyncMock):
    workflow_id = uuid4()
    execution_id = uuid4()
    
    # Mock WorkflowRepository.get_by_id
    mock_workflow = Workflow(id=workflow_id, project_id=uuid4(), workflow_type="test")
    
    # Setup session.execute mock
    result = Mock()
    # First call for Workflow
    result.scalar_one_or_none.return_value = mock_workflow
    session.execute.return_value = result
    
    # Mock WorkflowExecution creation
    # The repository.create will call session.add, session.commit, session.refresh
    # Our session fixture already mocks these.
    
    mock_task = Mock()
    mock_task.id = "task-async-123"
    
    with patch("apps.api.services.workflow_queue.celery_app.send_task", return_value=mock_task):
        response = await client.post(f"/workflows/{workflow_id}/enqueue")
        
        assert response.status_code == 202
        data = response.json()
        assert "execution_id" in data
        assert data["task_id"] == "task-async-123"
        assert data["status"] == "QUEUED"
        
        # Verify session interactions
        assert session.add.called
        assert session.commit.called

@pytest.mark.asyncio
async def test_worker_task_lifecycle_execution(session: AsyncMock):
    from apps.worker.tasks import _execute_workflow_execution_async
    from apps.api.domain.models import WorkflowExecution, Workflow
    
    execution_id = uuid4()
    workflow_id = uuid4()
    
    mock_execution = WorkflowExecution(id=execution_id, workflow_id=workflow_id)
    mock_workflow = Workflow(id=workflow_id, project_id=uuid4(), workflow_type="test")
    
    # Mock database and session
    with patch("apps.worker.tasks.Database") as mock_db_class:
        mock_db_instance = mock_db_class.return_value
        mock_db_instance.session_factory.return_value.__aenter__.return_value = session
        
        # Mock repository lookups
        # We need to handle multiple session.execute calls
        # 1. execution_repo.get_by_id
        # 2. workflow_repo.get_by_id
        # 3. step_repo.list_by_workflow (inside runtime.run)
        
        exec_result = Mock()
        exec_result.scalar_one_or_none.return_value = mock_execution
        
        wf_result = Mock()
        wf_result.scalar_one_or_none.return_value = mock_workflow
        
        steps_result = Mock()
        steps_result.scalars.return_value.all.return_value = []
        
        session.execute.side_effect = [exec_result, wf_result, steps_result]
        
        # Mock runtime to avoid full validation/execution logic complexity in integration test
        with patch("apps.worker.tasks.WorkflowRuntime") as mock_runtime_class:
            mock_runtime = mock_runtime_class.return_value
            mock_runtime.run = AsyncMock(return_value={"status": "completed", "execution_id": execution_id})
            
            mock_db_instance.dispose = AsyncMock()
            
            result = await _execute_workflow_execution_async(str(execution_id))
            
            assert result["status"] == "completed"
            mock_runtime.run.assert_called_once_with(mock_workflow, execution_id=execution_id)
            # Verify cleanup
            assert mock_db_instance.dispose.called
