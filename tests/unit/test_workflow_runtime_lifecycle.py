import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import UTC, datetime
from apps.api.workflow.runtime import WorkflowRuntime
from apps.api.domain.models import WorkflowExecutionStatus, WorkflowStepStatus, JobStatus

@pytest.fixture
def repositories():
    return {
        "job": AsyncMock(),
        "execution": AsyncMock(),
        "step": AsyncMock(),
        "history": AsyncMock(),
        "error": AsyncMock(),
        "metric": AsyncMock(),
    }

@pytest.mark.asyncio
async def test_run_with_existing_execution_id(repositories):
    runtime = WorkflowRuntime(
        repositories["job"],
        repositories["execution"],
        repositories["step"],
        repositories["history"],
        repositories["error"],
        repositories["metric"],
    )
    
    workflow = MagicMock()
    workflow.id = uuid4()
    execution_id = uuid4()
    
    mock_execution = MagicMock()
    mock_execution.id = execution_id
    mock_execution.status = WorkflowExecutionStatus.PENDING
    
    repositories["execution"].get_by_id.return_value = mock_execution
    repositories["execution"].update.return_value = mock_execution
    repositories["step"].list_by_workflow.return_value = []
    
    with patch.object(runtime.validator, "validate") as mock_validate:
        mock_validate.return_value = MagicMock(valid=True)
        
        result = await runtime.run(workflow, execution_id=execution_id)
        
        assert result["status"] == "completed"
        repositories["execution"].get_by_id.assert_called_once_with(execution_id)
        repositories["execution"].create.assert_not_called()

@pytest.mark.asyncio
async def test_run_validation_failure_with_execution_id(repositories):
    runtime = WorkflowRuntime(
        repositories["job"],
        repositories["execution"],
        repositories["step"],
        repositories["history"],
        repositories["error"],
        repositories["metric"],
    )
    
    workflow = MagicMock()
    workflow.id = uuid4()
    execution_id = uuid4()
    
    repositories["step"].list_by_workflow.return_value = []
    
    with patch.object(runtime.validator, "validate") as mock_validate:
        mock_validate.return_value = MagicMock(valid=False, errors=["Invalid step"])
        
        result = await runtime.run(workflow, execution_id=execution_id)
        
        assert result["status"] == "failed"
        repositories["error"].create.assert_called_once()
        repositories["execution"].update.assert_called()
        # Verify that the execution was marked as FAILED
        # The update might be called multiple times (initial running, then failed)
        failed_update = next((call for call in repositories["execution"].update.call_args_list 
                             if call.args[1].get("status") == WorkflowExecutionStatus.FAILED), None)
        assert failed_update is not None

@pytest.mark.asyncio
async def test_run_step_failure_persistence(repositories):
    runtime = WorkflowRuntime(
        repositories["job"],
        repositories["execution"],
        repositories["step"],
        repositories["history"],
        repositories["error"],
        repositories["metric"],
    )
    
    workflow = MagicMock()
    workflow.id = uuid4()
    
    step = MagicMock()
    step.id = uuid4()
    step.name = "Test Step"
    step.config = {}
    step.status = WorkflowStepStatus.PENDING
    
    repositories["step"].list_by_workflow.return_value = [step]
    
    mock_execution = MagicMock()
    mock_execution.id = uuid4()
    mock_execution.status = WorkflowExecutionStatus.PENDING
    repositories["execution"].create.return_value = mock_execution
    repositories["execution"].update.return_value = mock_execution
    
    mock_job = MagicMock()
    mock_job.id = uuid4()
    repositories["job"].create.return_value = mock_job
    
    # Force step execution failure
    # 1. job update to RUNNING
    # 2. job update to COMPLETED (we want this to fail)
    # Actually, in runtime.py:
    # updated_job = await self.job_repository.update(job.id, {"status": JobStatus.RUNNING})
    # updated_job = await self.job_repository.update(job.id, {"status": JobStatus.COMPLETED, ...})
    
    repositories["job"].update.side_effect = [mock_job, Exception("Execution failed"), mock_job]
    
    with patch.object(runtime.validator, "validate") as mock_validate:
        mock_validate.return_value = MagicMock(valid=True)
        
        result = await runtime.run(workflow)
        
        assert result["status"] == "failed"
        # Check if error was recorded
        repositories["error"].create.assert_called_once()
        # Check if job was updated to FAILED (this is the 3rd call in side_effect)
        assert repositories["job"].update.call_count >= 3
        # Check if execution was updated to FAILED
        failed_exec_update = next((call for call in repositories["execution"].update.call_args_list 
                                 if call.args[1].get("status") == WorkflowExecutionStatus.FAILED), None)
        assert failed_exec_update is not None
