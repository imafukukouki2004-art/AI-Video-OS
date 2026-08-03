import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from apps.worker.tasks import _execute_workflow_execution_async

@pytest.mark.asyncio
async def test_execute_workflow_execution_async_success():
    execution_id = uuid4()
    workflow_id = uuid4()
    
    # Mock models
    mock_execution = MagicMock()
    mock_execution.workflow_id = workflow_id
    
    mock_workflow = MagicMock()
    mock_workflow.id = workflow_id
    
    # Mock repositories
    mock_execution_repo = AsyncMock()
    mock_execution_repo.get_by_id.return_value = mock_execution
    
    mock_workflow_repo = AsyncMock()
    mock_workflow_repo.get_by_id.return_value = mock_workflow
    
    # Mock runtime
    mock_runtime = AsyncMock()
    mock_runtime.run.return_value = {"status": "completed", "execution_id": execution_id}
    
    # Mock database and dependencies
    with patch("apps.worker.tasks.Database") as mock_db_class, \
         patch("apps.worker.tasks.WorkflowRepository", return_value=mock_workflow_repo), \
         patch("apps.worker.tasks.WorkflowExecutionRepository", return_value=mock_execution_repo), \
         patch("apps.worker.tasks.JobRepository"), \
         patch("apps.worker.tasks.WorkflowStepRepository"), \
         patch("apps.worker.tasks.WorkflowExecutionHistoryRepository"), \
         patch("apps.worker.tasks.WorkflowExecutionErrorRepository"), \
         patch("apps.worker.tasks.WorkflowExecutionMetricRepository"), \
         patch("apps.worker.tasks.WorkflowRuntime", return_value=mock_runtime):
        
        # Setup DB session mock
        mock_session = AsyncMock()
        mock_db_instance = mock_db_class.return_value
        mock_db_instance.session_factory.return_value.__aenter__.return_value = mock_session
        mock_db_instance.dispose = AsyncMock()
        
        result = await _execute_workflow_execution_async(str(execution_id))
        
        assert result["status"] == "completed"
        mock_execution_repo.get_by_id.assert_called_once_with(execution_id)
        mock_workflow_repo.get_by_id.assert_called_once_with(workflow_id)
        mock_runtime.run.assert_called_once_with(mock_workflow, execution_id=execution_id)

@pytest.mark.asyncio
async def test_execute_workflow_execution_async_not_found():
    execution_id = uuid4()
    
    mock_execution_repo = AsyncMock()
    mock_execution_repo.get_by_id.return_value = None
    
    with patch("apps.worker.tasks.Database") as mock_db_class, \
         patch("apps.worker.tasks.WorkflowExecutionRepository", return_value=mock_execution_repo), \
         patch("apps.worker.tasks.WorkflowRepository"), \
         patch("apps.worker.tasks.JobRepository"), \
         patch("apps.worker.tasks.WorkflowStepRepository"), \
         patch("apps.worker.tasks.WorkflowExecutionHistoryRepository"), \
         patch("apps.worker.tasks.WorkflowExecutionErrorRepository"), \
         patch("apps.worker.tasks.WorkflowExecutionMetricRepository"):
        
        mock_session = AsyncMock()
        mock_db_instance = mock_db_class.return_value
        mock_db_instance.session_factory.return_value.__aenter__.return_value = mock_session
        mock_db_instance.dispose = AsyncMock()
        
        result = await _execute_workflow_execution_async(str(execution_id))
        
        assert result["status"] == "failed"
        assert result["error"] == "Execution not found"
