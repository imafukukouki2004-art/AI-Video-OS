"""Integration tests for Workflow Artifact registration and reference."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from apps.api.ai_providers.base import AIResponse
from apps.api.domain.models import (
    Workflow,
    WorkflowArtifact,
    WorkflowExecution,
    WorkflowExecutionStatus,
    WorkflowStep,
)
from apps.api.workflow.runtime import WorkflowRuntime


@pytest.fixture
def mock_repos():
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


@pytest.fixture
def runtime(mock_repos):
    return WorkflowRuntime(
        mock_repos["job"],
        mock_repos["execution"],
        mock_repos["step"],
        mock_repos["history"],
        mock_repos["error"],
        mock_repos["metric"],
        mock_repos["artifact"],
        mock_repos["asset"],
        MagicMock(),
    )


@pytest.mark.asyncio
async def test_workflow_runtime_records_artifact(runtime, mock_repos):
    workflow_id = uuid4()
    execution_id = uuid4()
    step_id = uuid4()
    asset_id = uuid4()
    artifact_id = uuid4()

    workflow = Workflow(id=workflow_id)
    step = WorkflowStep(
        id=step_id,
        workflow_id=workflow_id,
        name="generate_image",
        step_type="ai",
        order=0,
        config={"provider": "mock", "operation": "text_generation", "prompt": "test"},
    )

    execution = WorkflowExecution(
        id=execution_id, workflow_id=workflow_id, status=WorkflowExecutionStatus.PENDING
    )

    mock_repos["step"].list_by_workflow.return_value = [step]
    mock_repos["execution"].get_by_id.return_value = execution
    mock_repos["execution"].update.return_value = execution
    mock_repos["job"].create.return_value = AsyncMock(id=uuid4())
    mock_repos["job"].update.return_value = AsyncMock()
    mock_repos["artifact"].create.return_value = WorkflowArtifact(id=artifact_id)

    # Mock AI Provider to return artifact
    mock_ai_res = AIResponse(
        content="Generated Image Content",
        artifact_type="image",
        asset_id=asset_id,
        metadata={"width": 1024},
    )

    with patch("apps.api.ai_providers.factory.AIProviderFactory.create") as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.generate_text.return_value = mock_ai_res
        mock_factory.return_value = mock_provider

        await runtime.run(workflow, execution_id=execution_id)

        # Verify artifact registration
        mock_repos["artifact"].create.assert_called_once()
        args, _ = mock_repos["artifact"].create.call_args
        artifact_in = args[0]
        assert artifact_in.artifact_type == "image"
        assert artifact_in.asset_id == asset_id


@pytest.mark.asyncio
async def test_workflow_runtime_artifact_reference(runtime, mock_repos):
    workflow_id = uuid4()
    execution_id = uuid4()
    step1_id = uuid4()
    step2_id = uuid4()
    asset_id = uuid4()
    artifact_id = uuid4()

    workflow = Workflow(id=workflow_id)
    step1 = WorkflowStep(
        id=step1_id,
        workflow_id=workflow_id,
        name="step1",
        step_type="ai",
        order=0,
        config={"provider": "mock", "operation": "text_generation", "prompt": "gen"},
    )
    step2 = WorkflowStep(
        id=step2_id,
        workflow_id=workflow_id,
        name="step2",
        step_type="ai",
        order=1,
        config={
            "provider": "mock",
            "operation": "text_generation",
            "prompt": "Ref: {{step1.artifact}} and {{step1.asset}}",
        },
    )

    execution = WorkflowExecution(
        id=execution_id, workflow_id=workflow_id, status=WorkflowExecutionStatus.PENDING
    )

    mock_repos["step"].list_by_workflow.return_value = [step1, step2]
    mock_repos["execution"].get_by_id.return_value = execution
    mock_repos["execution"].update.return_value = execution
    mock_repos["job"].create.side_effect = [AsyncMock(id=uuid4()), AsyncMock(id=uuid4())]
    mock_repos["job"].update.return_value = AsyncMock()
    mock_repos["artifact"].create.return_value = WorkflowArtifact(id=artifact_id)

    # Step 1 returns artifact and asset
    res1 = AIResponse(content="res1", artifact_type="image", asset_id=asset_id)
    # Step 2 just returns text
    res2 = AIResponse(content="res2")

    with patch("apps.api.ai_providers.factory.AIProviderFactory.create") as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.generate_text.side_effect = [res1, res2]
        mock_factory.return_value = mock_provider

        await runtime.run(workflow, execution_id=execution_id)

        # Verify Step 2 received resolved prompt
        # The prompt was "Ref: {{step1.artifact}} and {{step1.asset}}"
        # Resolved should be "Ref: <artifact_id> and <asset_id>"
        expected_prompt = f"Ref: {artifact_id} and {asset_id}"
        mock_provider.generate_text.assert_any_call(prompt=expected_prompt)


@pytest.mark.asyncio
async def test_workflow_runtime_invalid_artifact_reference(runtime, mock_repos):
    workflow_id = uuid4()
    execution_id = uuid4()
    step_id = uuid4()

    workflow = Workflow(id=workflow_id)
    step = WorkflowStep(
        id=step_id,
        workflow_id=workflow_id,
        name="step1",
        step_type="ai",
        order=0,
        config={
            "provider": "mock",
            "operation": "text_generation",
            "prompt": "{{non_existent.artifact}}",
        },
    )

    execution = WorkflowExecution(
        id=execution_id, workflow_id=workflow_id, status=WorkflowExecutionStatus.PENDING
    )

    mock_repos["step"].list_by_workflow.return_value = [step]
    mock_repos["execution"].get_by_id.return_value = execution
    mock_repos["execution"].update.return_value = execution

    result = await runtime.run(workflow, execution_id=execution_id)

    assert result["status"] == "failed"
    assert "Workflow validation failed" in result["error"]
    mock_repos["error"].create.assert_called()
