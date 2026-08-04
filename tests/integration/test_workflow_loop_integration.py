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
async def test_workflow_runtime_loop_execution_and_aggregation(repositories):
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

    # Step 1: Generates a list
    step1 = WorkflowStep(
        id=uuid4(),
        name="Step1",
        step_type="ai",
        order=1,
        config={"provider": "mock", "operation": "text_generation"},
        status=WorkflowStepStatus.PENDING,
    )

    # Step 2: Loops over Step 1's output
    step2 = WorkflowStep(
        id=uuid4(),
        name="Step2",
        step_type="ai",
        order=2,
        config={"provider": "mock", "operation": "text_generation", "prompt": "Process {{item}}"},
        loop_source="{{Step1.output}}",
        loop_variable="item",
        status=WorkflowStepStatus.PENDING,
    )

    repositories["step"].list_by_workflow.return_value = [step1, step2]
    repositories["execution"].create.return_value = MagicMock(id=uuid4(), status="pending")
    repositories["execution"].update.return_value = AsyncMock(id=uuid4(), status="running")
    repositories["job"].create.return_value = AsyncMock(id=uuid4())
    repositories["job"].update = AsyncMock()

    # Mock AI Provider
    mock_provider = AsyncMock()

    with (
        patch.object(runtime.validator, "validate") as mock_validate,
        patch("apps.api.workflow.runtime.AIProviderFactory.create", return_value=mock_provider),
    ):
        mock_validate.return_value = MagicMock(valid=True)

        # Step 1 execution returns a LIST
        mock_res1 = MagicMock(content=["a", "b"], metadata={"provider": "mock"})
        mock_res1.artifact_type = None
        mock_res1.asset_id = None
        mock_res2 = MagicMock(content="Result A", metadata={"provider": "mock"})
        mock_res2.artifact_type = None
        mock_res2.asset_id = None
        mock_res3 = MagicMock(content="Result B", metadata={"provider": "mock"})
        mock_res3.artifact_type = None
        mock_res3.asset_id = None
        mock_provider.generate_text.side_effect = [mock_res1, mock_res2, mock_res3]

        result = await runtime.run(workflow)

        assert result["status"] == "completed"

        # Step 1 (1 job) + Step 2 (2 iterations = 2 jobs) = 3 jobs
        assert repositories["job"].create.call_count == 3


@pytest.mark.asyncio
async def test_workflow_runtime_loop_invalid_source_error(repositories):
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

    step = WorkflowStep(
        id=uuid4(),
        name="LoopStep",
        step_type="ai",
        order=1,
        config={"provider": "mock"},
        loop_source="{{missing.output}}",
        loop_variable="item",
        status=WorkflowStepStatus.PENDING,
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
