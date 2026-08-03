from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from apps.api.domain.models import WorkflowStepStatus
from apps.api.workflow.runtime import WorkflowRuntime


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
async def test_workflow_runtime_openai_provider_selection(repositories):
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
    step.name = "OpenAI Step"
    step.config = {"provider": "openai", "temperature": 0.7}
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
    
    # Mock AIProviderFactory and OpenAIProvider
    mock_provider = AsyncMock()
    mock_res = MagicMock()
    mock_res.content = "OpenAI Generated Content"
    mock_res.metadata = {"provider": "openai"}
    mock_provider.generate_text.return_value = mock_res
    
    with patch.object(runtime.validator, "validate") as mock_validate, patch(
        "apps.api.workflow.runtime.AIProviderFactory.create", return_value=mock_provider
    ) as mock_factory_create:
        
        mock_validate.return_value = MagicMock(valid=True)
        
        result = await runtime.run(workflow)
        
        assert result["status"] == "completed"
        # Verify factory was called with 'openai'
        mock_factory_create.assert_called_once_with("openai")
        # Verify provider was called with correct prompt and config
        mock_provider.generate_text.assert_called_once()
        args, kwargs = mock_provider.generate_text.call_args
        assert kwargs["prompt"] == "OpenAI Step"
        assert kwargs["temperature"] == 0.7
        
        # Verify job was updated with OpenAI output
        args, kwargs = repositories["job"].update.call_args_list[-1]
        update_data = args[1]
        assert update_data["output_data"]["result"] == "OpenAI Generated Content"
