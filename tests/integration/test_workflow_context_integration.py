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
async def test_workflow_runtime_variable_resolution_multi_step(repositories):
    runtime = WorkflowRuntime(
        repositories["job"],
        repositories["execution"],
        repositories["step"],
        repositories["history"],
        repositories["error"],
        repositories["metric"],
        repositories["artifact"],
        repositories["asset"],
    )

    workflow = MagicMock()
    workflow.id = uuid4()

    # Step 1: Generates text
    step1 = WorkflowStep(
        id=uuid4(),
        name="Step1",
        step_type="ai",
        order=1,
        config={"provider": "mock", "operation": "text_generation", "prompt": "Prompt 1"},
        status=WorkflowStepStatus.PENDING,
    )

    # Step 2: Uses Step 1's output
    step2 = WorkflowStep(
        id=uuid4(),
        name="Step2",
        step_type="ai",
        order=2,
        config={
            "provider": "mock",
            "operation": "text_generation",
            "prompt": "Summarize this: {{Step1.output}}",
        },
        status=WorkflowStepStatus.PENDING,
    )

    repositories["step"].list_by_workflow.return_value = [step1, step2]

    # Mock executions and jobs
    repositories["execution"].create.return_value = MagicMock(id=uuid4(), status="pending")
    repositories["execution"].update.return_value = MagicMock(id=uuid4(), status="running")
    repositories["job"].create.return_value = MagicMock(id=uuid4())
    repositories["job"].update.return_value = MagicMock(id=uuid4())

    # Mock AI Provider
    mock_provider = AsyncMock()
    # Step 1 returns "Output 1"
    mock_res1 = MagicMock(content="Output 1", metadata={"provider": "mock"})
    mock_res1.artifact_type = None
    mock_res1.asset_id = None
    mock_res2 = MagicMock(content="Output 2", metadata={"provider": "mock"})
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

        # Verify provider calls
        assert mock_provider.generate_text.call_count == 2

        # Verify Step 2 received the resolved prompt
        _, kwargs = mock_provider.generate_text.call_args_list[1]
        assert kwargs["prompt"] == "Summarize this: Output 1"


@pytest.mark.asyncio
async def test_workflow_runtime_unresolved_variable_error_persistence(repositories):
    runtime = WorkflowRuntime(
        repositories["job"],
        repositories["execution"],
        repositories["step"],
        repositories["history"],
        repositories["error"],
        repositories["metric"],
        repositories["artifact"],
        repositories["asset"],
    )

    workflow = MagicMock()
    workflow.id = uuid4()

    step = WorkflowStep(
        id=uuid4(),
        name="ErrorStep",
        step_type="ai",
        order=1,
        config={"prompt": "Use missing: {{missing.output}}"},
        status=WorkflowStepStatus.PENDING,
    )

    repositories["step"].list_by_workflow.return_value = [step]
    repositories["execution"].create.return_value = MagicMock(id=uuid4(), status="pending")
    repositories["execution"].update.return_value = MagicMock(id=uuid4(), status="running")
    repositories["job"].create.return_value = MagicMock(id=uuid4())

    with patch.object(runtime.validator, "validate") as mock_validate:
        mock_validate.return_value = MagicMock(valid=True)

        result = await runtime.run(workflow)

        assert result["status"] == "failed"
        assert "Variable resolution failed" in result["error"]

        # Verify error persistence
        repositories["error"].create.assert_called_once()
        args, _ = repositories["error"].create.call_args
        error_in = args[0]
        assert "Unresolved variable" in error_in.error_message
