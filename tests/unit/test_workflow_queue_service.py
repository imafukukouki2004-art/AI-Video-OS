import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from apps.api.services.workflow_queue import WorkflowQueueService
from apps.api.repositories import WorkflowExecutionRepository

@pytest.fixture
def execution_repository():
    return AsyncMock(spec=WorkflowExecutionRepository)

@pytest.mark.asyncio
async def test_enqueue_execution(execution_repository):
    service = WorkflowQueueService(execution_repository)
    execution_id = uuid4()
    
    # Mock celery_app.send_task
    mock_task = MagicMock()
    mock_task.id = "test-task-id"
    
    with patch("apps.api.services.workflow_queue.celery_app.send_task", return_value=mock_task) as mock_send:
        task_id = await service.enqueue_execution(execution_id)
        
        assert task_id == "test-task-id"
        mock_send.assert_called_once_with(
            "apps.worker.tasks.execute_workflow",
            args=[str(execution_id)],
            queue="ai-video-os"
        )
        execution_repository.update.assert_called_once_with(
            execution_id, {"task_id": "test-task-id"}
        )

@pytest.mark.asyncio
async def test_get_task_status(execution_repository):
    service = WorkflowQueueService(execution_repository)
    task_id = "test-task-id"
    
    # Mock celery_app.AsyncResult
    mock_result = MagicMock()
    mock_result.status = "SUCCESS"
    
    with patch("apps.api.services.workflow_queue.celery_app.AsyncResult", return_value=mock_result):
        status = await service.get_task_status(task_id)
        assert status == "SUCCESS"
