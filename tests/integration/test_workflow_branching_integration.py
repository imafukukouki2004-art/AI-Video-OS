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
        "artifact": AsyncMock(),
        "asset": AsyncMock(),
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
        repositories["artifact"],
        repositories["asset"],
            MagicMock(),
        )

    workflow = MagicMock()
    workflow.id = uuid4()

    step_true_id = uuid4()
    step_false_id = uuid4()

    # Step 1: Generates "yes"
    step1 = WorkflowStep(
        id=uuid4(),
        name="Step1",
        step_type="ai",
        order=1,
        config={"provider": "mock", "operation": "text_generation"},
        condition='{{Step1.output}} == "yes"',
        next_step_on_true=step_true_id,
        next_step_on_false=step_false_id,
        status=WorkflowStepStatus.PENDING,
    )

    # Step True: Should be executed
    step_true = WorkflowStep(
        id=step_true_id,
        name="StepTrue",
        step_type="ai",
        order=3,
        config={"provider": "mock"},
        status=WorkflowStepStatus.PENDING,
    )

    # Step False: Should NOT be executed
    step_false = WorkflowStep(
        id=step_false_id,
        name="StepFalse",
        step_type="ai",
        order=2,
        config={"provider": "mock"},
        status=WorkflowStepStatus.PENDING,
    )

    # Order: 1, False, True. Branching from 1 to True will skip False.
    repositories["step"].list_by_workflow.return_value = [step1, step_false, step_true]
    repositories["execution"].create.return_value = MagicMock(id=uuid4(), status="pending")
    repositories["execution"].update.return_value = AsyncMock(id=uuid4(), status="running")
    repositories["job"].create.return_value = AsyncMock(id=uuid4())
    repositories["job"].update = AsyncMock()

    # Mock AI Provider
    mock_provider = AsyncMock()
    mock_res1 = MagicMock(content="yes", metadata={"provider": "mock"})
    mock_res1.artifact_type = None
    mock_res1.asset_id = None
    mock_res2 = MagicMock(content="done", metadata={"provider": "mock"})
    mock_res2.artifact_type = None
    mock_res2.asset_id = None
    mock_provider.generate_text.side_effect = [mock_res1, mock_res2]

    with (
        patch.object(runtime.validator, "validate") as mock_validate,
        patch("apps.api.workflow.runtime.AIProviderFactory.create", return_value=mock_provider),
    ):
        mock_validate.return_value = MagicMock(valid=True)

        result = await runtime.run(workflow)

        assert result["status"] == "completed"

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
        repositories["artifact"],
        repositories["asset"],
            MagicMock(),
        )

    workflow = MagicMock()
    workflow.id = uuid4()

    step_true_id = uuid4()
    step_false_id = uuid4()

    # Step 1: Generates "no"
    step1 = WorkflowStep(
        id=uuid4(),
        name="Step1",
        step_type="ai",
        order=1,
        config={"provider": "mock", "operation": "text_generation"},
        condition='{{Step1.output}} == "yes"',
        next_step_on_true=step_true_id,
        next_step_on_false=step_false_id,
        status=WorkflowStepStatus.PENDING,
    )

    # Step True: Should NOT be executed
    step_true = WorkflowStep(
        id=step_true_id,
        name="StepTrue",
        step_type="ai",
        order=2,
        config={"provider": "mock"},
        status=WorkflowStepStatus.PENDING,
    )

    # Step False: Should be executed
    step_false = WorkflowStep(
        id=step_false_id,
        name="StepFalse",
        step_type="ai",
        order=3,
        config={"provider": "mock"},
        status=WorkflowStepStatus.PENDING,
    )

    # Order: 1, True, False. Branching from 1 to False will skip True.
    repositories["step"].list_by_workflow.return_value = [step1, step_true, step_false]
    repositories["execution"].create.return_value = MagicMock(id=uuid4(), status="pending")
    repositories["execution"].update.return_value = AsyncMock(id=uuid4(), status="running")
    repositories["job"].create.return_value = AsyncMock(id=uuid4())
    repositories["job"].update = AsyncMock()

    # Mock AI Provider
    mock_provider = AsyncMock()
    mock_res1 = MagicMock(content="no", metadata={"provider": "mock"})
    mock_res1.artifact_type = None
    mock_res1.asset_id = None
    mock_res2 = MagicMock(content="done", metadata={"provider": "mock"})
    mock_res2.artifact_type = None
    mock_res2.asset_id = None
    mock_provider.generate_text.side_effect = [mock_res1, mock_res2]

    with (
        patch.object(runtime.validator, "validate") as mock_validate,
        patch("apps.api.workflow.runtime.AIProviderFactory.create", return_value=mock_provider),
    ):
        mock_validate.return_value = MagicMock(valid=True)

        result = await runtime.run(workflow)

        assert result["status"] == "completed"

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
        repositories["artifact"],
        repositories["asset"],
            MagicMock(),
        )

    workflow = MagicMock()
    workflow.id = uuid4()

    # Step 1: Points to non-existent target
    step1 = WorkflowStep(
        id=uuid4(),
        name="Step1",
        step_type="ai",
        order=1,
        config={"provider": "mock"},
        condition='{{Step1.output}} == "yes"',
        next_step_on_true=uuid4(),  # Missing
        status=WorkflowStepStatus.PENDING,
    )

    repositories["step"].list_by_workflow.return_value = [step1]
    repositories["execution"].create.return_value = MagicMock(id=uuid4(), status="pending")
    repositories["execution"].update.return_value = AsyncMock(id=uuid4(), status="running")
    repositories["job"].create.return_value = AsyncMock(id=uuid4())
    repositories["job"].update = AsyncMock()

    mock_provider = AsyncMock()
    mock_res = MagicMock(content="yes", metadata={"provider": "mock"})
    mock_res.artifact_type = None
    mock_res.asset_id = None
    mock_provider.generate_text.return_value = mock_res

    with (
        patch.object(runtime.validator, "validate") as mock_validate,
        patch("apps.api.workflow.runtime.AIProviderFactory.create", return_value=mock_provider),
    ):
        mock_validate.return_value = MagicMock(valid=True)

        result = await runtime.run(workflow)

        assert result["status"] == "failed"
        assert "Target step" in result["error"]
        assert "not found" in result["error"]
