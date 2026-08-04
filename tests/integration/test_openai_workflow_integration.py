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
async def test_workflow_runtime_openai_text_generation_mapping(repositories):
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
        name="AI Text Step",
        step_type="ai",
        order=1,
        config={
            "provider": "openai",
            "operation": "text_generation",
            "prompt": "Custom Prompt",
            "system_prompt": "You are a helpful assistant",
            "temperature": 0.5,
        },
        status=WorkflowStepStatus.PENDING,
    )

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

    # Mock OpenAI Provider
    mock_provider = AsyncMock()
    mock_res = MagicMock()
    mock_res.content = "OpenAI response with custom mapping"
    mock_res.metadata = {"provider": "openai"}
    mock_res.artifact_type = None
    mock_res.asset_id = None
    mock_provider.generate_text.return_value = mock_res

    with (
        patch.object(runtime.validator, "validate") as mock_validate,
        patch("apps.api.workflow.runtime.AIProviderFactory.create", return_value=mock_provider),
    ):
        mock_validate.return_value = MagicMock(valid=True)

        result = await runtime.run(workflow)

        assert result["status"] == "completed"

        # Verify Input Mapping
        mock_provider.generate_text.assert_called_once()
        _, kwargs = mock_provider.generate_text.call_args
        assert kwargs["prompt"] == "Custom Prompt"
        assert kwargs["system_prompt"] == "You are a helpful assistant"
        assert kwargs["temperature"] == 0.5
        # Ensure metadata like provider/operation are NOT passed to generate_text
        assert "provider" not in kwargs
        assert "operation" not in kwargs

        # Verify Output Persistence
        args, _ = repositories["job"].update.call_args_list[-1]
        update_data = args[1]
        assert update_data["output_data"]["result"] == "OpenAI response with custom mapping"


@pytest.mark.asyncio
async def test_workflow_runtime_unsupported_operation_error(repositories):
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
        name="Invalid Step",
        step_type="ai",
        order=1,
        config={"operation": "unsupported_op"},
        status=WorkflowStepStatus.PENDING,
    )

    repositories["step"].list_by_workflow.return_value = [step]

    mock_execution = MagicMock()
    mock_execution.id = uuid4()
    repositories["execution"].create.return_value = mock_execution
    repositories["execution"].update.return_value = mock_execution

    mock_job = MagicMock()
    mock_job.id = uuid4()
    repositories["job"].create.return_value = mock_job

    with patch.object(runtime.validator, "validate") as mock_validate:
        mock_validate.return_value = MagicMock(valid=True)

        result = await runtime.run(workflow)

        assert result["status"] == "failed"
        assert "Unsupported AI operation" in result["error"]

        # Verify Error Persistence
        repositories["error"].create.assert_called_once()
        args, _ = repositories["error"].create.call_args
        error_in = args[0]
        assert error_in.error_code == "STEP_EXECUTION_FAILED"
        assert "Unsupported AI operation" in error_in.error_message


@pytest.mark.asyncio
async def test_mock_provider_compatibility(repositories):
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
        name="Mock Step",
        step_type="ai",
        order=1,
        config={
            "provider": "mock",
            "operation": "text_generation",
            "prompt": "Mock Prompt",
            "system_prompt": "Mock System",
        },
        status=WorkflowStepStatus.PENDING,
    )

    repositories["step"].list_by_workflow.return_value = [step]
    repositories["execution"].create.return_value = MagicMock(id=uuid4(), status="pending")
    repositories["execution"].update.return_value = MagicMock(id=uuid4(), status="running")
    repositories["job"].create.return_value = MagicMock(id=uuid4())

    with patch.object(runtime.validator, "validate") as mock_validate:
        mock_validate.return_value = MagicMock(valid=True)

        result = await runtime.run(workflow)

        assert result["status"] == "completed"
        # Verify output from Mock Provider
        args, _ = repositories["job"].update.call_args_list[-1]
        update_data = args[1]
        assert "Mock response for: Mock Prompt" in update_data["output_data"]["result"]
        assert update_data["output_data"]["metadata"]["system_prompt"] == "Mock System"
