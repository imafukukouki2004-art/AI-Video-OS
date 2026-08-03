import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from apps.api.workflow.runtime import WorkflowRuntime
from apps.api.domain.models import WorkflowStepStatus, JobStatus

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
async def test_workflow_runtime_ai_provider_integration(repositories):
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
    step.name = "AI Step"
    step.config = {"provider": "mock"}
    step.status = WorkflowStepStatus.PENDING
    
    repositories["step"].list_by_workflow.return_value = [step]
    
    mock_execution = MagicMock()
    mock_execution.id = uuid4()
    mock_execution.status = "pending"
    repositories["execution"].create.return_value = mock_execution
    repositories["execution"].update.return_value = mock_execution
    
    mock_job = MagicMock()
    mock_job.id = uuid4()
    repositories["job"].create.return_value = mock_job
    repositories["job"].update.return_value = mock_job
    
    with patch.object(runtime.validator, "validate") as mock_validate:
        mock_validate.return_value = MagicMock(valid=True)
        
        result = await runtime.run(workflow)
        
        assert result["status"] == "completed"
        # Verify job was updated with AI output
        args, kwargs = repositories["job"].update.call_args_list[-1]
        # Repository update is called with (id, data_dict) or (id, schema=data_dict)
        # Based on runtime.py: await self.job_repository.update(job.id, {"status": JobStatus.COMPLETED, "output_data": result_data})
        # The data is in args[1]
        update_data = args[1]
        assert "output_data" in update_data
        assert "mock" in update_data["output_data"]["result"].lower()
