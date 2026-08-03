from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from apps.api.domain.models import WorkflowStep, WorkflowStepStatus
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
async def test_workflow_runtime_loop_execution_and_aggregation(repositories):
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
    
    # Step 1: Generates a list
    step1 = WorkflowStep(
        id=uuid4(),
        name="Step1",
        step_type="ai",
        order=1,
        config={"provider": "mock", "operation": "text_generation"},
        status=WorkflowStepStatus.PENDING
    )
    
    # Step 2: Loops over Step 1's output
    step2 = WorkflowStep(
        id=uuid4(),
        name="Step2",
        step_type="ai",
        order=2,
        config={
            "provider": "mock", 
            "operation": "text_generation", 
            "prompt": "Process {{item}}"
        },
        loop_source="{{Step1.output}}",
        loop_variable="item",
        status=WorkflowStepStatus.PENDING
    )
    
    repositories["step"].list_by_workflow.return_value = [step1, step2]
    repositories["execution"].create.return_value = MagicMock(id=uuid4(), status="pending")
    repositories["execution"].update.return_value = AsyncMock(id=uuid4(), status="running")
    repositories["job"].create.return_value = AsyncMock(id=uuid4())
    repositories["job"].update = AsyncMock()
    
    # Mock AI Provider
    mock_provider = AsyncMock()
    # Step 1 returns a LIST (simulated as a string forced into context as a list)
    # Actually, let's make Step 1 return a list directly in our mocked runtime flow.
    # Wait, the runtime expects provider.generate_text to return AIResponse.content as string.
    # For TICKET-028, loop_source must be an array.
    
    # We need to simulate Step 1 outputting a list. 
    # Since our current text_generation returns string, we'll mock the context registration.
    
    with patch.object(runtime.validator, "validate") as mock_validate, \
         patch("apps.api.workflow.runtime.AIProviderFactory.create", return_value=mock_provider):
        
        mock_validate.return_value = MagicMock(valid=True)
        
        # Manually inject a list into Step 1's output in the context during execution
        # We can't easily do that without patching the runtime's internal context.
        # Let's mock provider.generate_text to return different things.
        
        # Step 1 execution
        mock_provider.generate_text.side_effect = [
            MagicMock(content=["a", "b"], metadata={"provider": "mock"}), # Step 1 (Loop Source)
            MagicMock(content="Result A", metadata={"provider": "mock"}), # Step 2 Iteration 1
            MagicMock(content="Result B", metadata={"provider": "mock"})  # Step 2 Iteration 2
        ]
        
        result = await runtime.run(workflow)
        
        assert result["status"] == "completed"
        
        # Step 1 (1 job) + Step 2 (2 iterations = 2 jobs) = 3 jobs
        assert repositories["job"].create.call_count == 3
        
        # Verify aggregation
        # We can check if the final jobs returned in result include all 3
        assert len(result["jobs"]) == 3

@pytest.mark.asyncio
async def test_workflow_runtime_loop_invalid_source_error(repositories):
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
    
    step = WorkflowStep(
        id=uuid4(),
        name="LoopStep",
        step_type="ai",
        order=1,
        config={"provider": "mock"},
        loop_source="{{missing.output}}",
        loop_variable="item",
        status=WorkflowStepStatus.PENDING
    )
    
    repositories["step"].list_by_workflow.return_value = [step]
    repositories["execution"].create.return_value = MagicMock(id=uuid4(), status="pending")
    repositories["execution"].update.return_value = AsyncMock(id=uuid4(), status="running")
    
    with patch.object(runtime.validator, "validate") as mock_validate:
        mock_validate.return_value = MagicMock(valid=True)
        
        result = await runtime.run(workflow)
        
        assert result["status"] == "failed"
        assert "Loop resolution failed" in result["error"]
        
        # Verify error persistence
        repositories["error"].create.assert_called_once()
        args, _ = repositories["error"].create.call_args
        assert "Unresolved variable" in args[0].error_message
