import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from apps.api.workflow.runtime import WorkflowRuntime
from apps.api.domain.models import WorkflowStepStatus

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
async def test_workflow_runtime_branching_true_path(repositories):
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
    
    step_true_id = uuid4()
    step_false_id = uuid4()
    
    # Step 1: Generates "yes"
    step1 = MagicMock()
    step1.id = uuid4()
    step1.name = "Step1"
    step1.config = {"provider": "mock", "operation": "text_generation"}
    step1.condition = '{{Step1.output}} == "yes"'
    step1.next_step_on_true = step_true_id
    step1.next_step_on_false = step_false_id
    step1.status = WorkflowStepStatus.PENDING
    
    # Step True: Should be executed
    step_true = MagicMock()
    step_true.id = step_true_id
    step_true.name = "StepTrue"
    step_true.config = {"provider": "mock"}
    step_true.condition = None
    step_true.status = WorkflowStepStatus.PENDING
    
    # Step False: Should NOT be executed
    step_false = MagicMock()
    step_false.id = step_false_id
    step_false.name = "StepFalse"
    step_false.config = {"provider": "mock"}
    step_false.condition = None
    step_false.status = WorkflowStepStatus.PENDING
    
    # Order: 1, False, True. Branching from 1 to True will skip False.
    repositories["step"].list_by_workflow.return_value = [step1, step_false, step_true]
    repositories["execution"].create.return_value = MagicMock(id=uuid4(), status="pending")
    repositories["execution"].update.return_value = AsyncMock(id=uuid4(), status="running")
    repositories["job"].create.return_value = AsyncMock(id=uuid4())
    repositories["job"].update = AsyncMock()
    
    # Mock AI Provider
    mock_provider = AsyncMock()
    mock_provider.generate_text.side_effect = [
        MagicMock(content="yes", metadata={"provider": "mock"}), # Step 1
        MagicMock(content="done", metadata={"provider": "mock"}) # Step True
    ]

    with patch.object(runtime.validator, "validate") as mock_validate, \
         patch("apps.api.workflow.runtime.AIProviderFactory.create", return_value=mock_provider):
        
        mock_validate.return_value = MagicMock(valid=True)
        
        result = await runtime.run(workflow)
        
        assert result["status"] == "completed"
        # Step 1 and StepTrue should have jobs, but NOT StepFalse
        assert len(result["jobs"]) == 2
        
        # Verify specific steps executed
        # Job creation calls: 1 for Step1, 1 for StepTrue
        assert repositories["job"].create.call_count == 2
        call_args_list = repositories["job"].create.call_args_list
        executed_step_ids = [call[0][0].step_id for call in call_args_list]
        assert step1.id in executed_step_ids
        assert step_true.id in executed_step_ids
        assert step_false.id not in executed_step_ids

@pytest.mark.asyncio
async def test_workflow_runtime_branching_false_path(repositories):
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
    
    step_true_id = uuid4()
    step_false_id = uuid4()
    
    # Step 1: Generates "no"
    step1 = MagicMock()
    step1.id = uuid4()
    step1.name = "Step1"
    step1.config = {"provider": "mock", "operation": "text_generation"}
    step1.condition = '{{Step1.output}} == "yes"'
    step1.next_step_on_true = step_true_id
    step1.next_step_on_false = step_false_id
    step1.status = WorkflowStepStatus.PENDING
    
    # Step True: Should NOT be executed
    step_true = MagicMock()
    step_true.id = step_true_id
    step_true.name = "StepTrue"
    step_true.config = {"provider": "mock"}
    step_true.condition = None
    step_true.status = WorkflowStepStatus.PENDING
    
    # Step False: Should be executed
    step_false = MagicMock()
    step_false.id = step_false_id
    step_false.name = "StepFalse"
    step_false.config = {"provider": "mock"}
    step_false.condition = None
    step_false.status = WorkflowStepStatus.PENDING
    
    # Order: 1, True, False. Branching from 1 to False will skip True.
    repositories["step"].list_by_workflow.return_value = [step1, step_true, step_false]
    repositories["execution"].create.return_value = MagicMock(id=uuid4(), status="pending")
    repositories["execution"].update.return_value = AsyncMock(id=uuid4(), status="running")
    repositories["job"].create.return_value = AsyncMock(id=uuid4())
    repositories["job"].update = AsyncMock()
    
    # Mock AI Provider
    mock_provider = AsyncMock()
    mock_provider.generate_text.side_effect = [
        MagicMock(content="no", metadata={"provider": "mock"}), # Step 1
        MagicMock(content="done", metadata={"provider": "mock"}) # Step False
    ]

    with patch.object(runtime.validator, "validate") as mock_validate, \
         patch("apps.api.workflow.runtime.AIProviderFactory.create", return_value=mock_provider):
        
        mock_validate.return_value = MagicMock(valid=True)
        
        result = await runtime.run(workflow)
        
        assert result["status"] == "completed"
        assert len(result["jobs"]) == 2
        
        # Verify specific steps executed
        call_args_list = repositories["job"].create.call_args_list
        executed_step_ids = [call[0][0].step_id for call in call_args_list]
        assert step1.id in executed_step_ids
        assert step_false.id in executed_step_ids
        assert step_true.id not in executed_step_ids

@pytest.mark.asyncio
async def test_workflow_runtime_invalid_branch_target_error(repositories):
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
    
    # Step 1: Points to non-existent target
    step1 = MagicMock()
    step1.id = uuid4()
    step1.name = "Step1"
    step1.config = {"provider": "mock"}
    step1.condition = '{{Step1.output}} == "yes"'
    step1.next_step_on_true = uuid4() # Missing
    
    repositories["step"].list_by_workflow.return_value = [step1]
    repositories["execution"].create.return_value = MagicMock(id=uuid4(), status="pending")
    repositories["execution"].update.return_value = AsyncMock(id=uuid4(), status="running")
    repositories["job"].create.return_value = AsyncMock(id=uuid4())
    repositories["job"].update = AsyncMock()
    
    mock_provider = AsyncMock()
    mock_provider.generate_text.return_value = MagicMock(content="yes", metadata={"provider": "mock"})

    with patch.object(runtime.validator, "validate") as mock_validate, \
         patch("apps.api.workflow.runtime.AIProviderFactory.create", return_value=mock_provider):
        
        mock_validate.return_value = MagicMock(valid=True)
        
        result = await runtime.run(workflow)
        
        assert result["status"] == "failed"
        assert "Target step" in result["error"]
        assert "not found" in result["error"]
