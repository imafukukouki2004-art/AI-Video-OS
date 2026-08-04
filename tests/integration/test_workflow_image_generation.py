from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from apps.api.ai_providers.base import AIImageResponse
from apps.api.domain.models import (
    Workflow,
    WorkflowExecution,
    WorkflowExecutionStatus,
    WorkflowStep,
)
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
async def test_workflow_runtime_image_generation_flow(repositories):
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

    workflow_id = uuid4()
    workflow = Workflow(id=workflow_id)

    step_id = uuid4()
    step = WorkflowStep(
        id=step_id,
        workflow_id=workflow_id,
        name="ImageGen",
        step_type="ai",
        order=0,
        config={
            "provider": "openai",
            "operation": "image_generation",
            "prompt": "A beautiful landscape",
            "size": "1024x1024",
        },
    )

    execution_id = uuid4()
    execution = WorkflowExecution(
        id=execution_id, workflow_id=workflow_id, status=WorkflowExecutionStatus.PENDING
    )

    repositories["step"].list_by_workflow.return_value = [step]
    repositories["execution"].get_by_id.return_value = execution
    repositories["execution"].update.return_value = execution
    repositories["job"].create.return_value = AsyncMock(id=uuid4())
    repositories["job"].update.return_value = AsyncMock()
    
    asset_id = uuid4()
    repositories["asset"].create.return_value = MagicMock(id=asset_id)
    
    artifact_id = uuid4()
    repositories["artifact"].create.return_value = MagicMock(id=artifact_id)

    # Mock AI Provider for image generation
    mock_ai_res = AIImageResponse(
        image_url="https://example.com/generated.png",
        mime_type="image/png",
        metadata={"provider": "openai", "model": "dall-e-3"},
    )

    with (
        patch.object(runtime.validator, "validate") as mock_validate,
        patch("apps.api.ai_providers.factory.AIProviderFactory.create") as mock_factory,
    ):
        mock_validate.return_value = MagicMock(valid=True)
        mock_provider = AsyncMock()
        mock_provider.generate_image.return_value = mock_ai_res
        mock_factory.return_value = mock_provider

        result = await runtime.run(workflow, execution_id=execution_id)

        assert result["status"] == "completed"

        # 1. Verify Provider Call
        mock_provider.generate_image.assert_called_once()
        _, kwargs = mock_provider.generate_image.call_args
        assert kwargs["prompt"] == "A beautiful landscape"
        assert kwargs["size"] == "1024x1024"

        # 2. Verify Asset Registration
        repositories["asset"].create.assert_called_once()
        args, _ = repositories["asset"].create.call_args
        asset_in = args[0]
        assert asset_in.content_type == "image/png"
        assert "generated/" in asset_in.object_key

        # 3. Verify Artifact Registration
        repositories["artifact"].create.assert_called_once()
        args, _ = repositories["artifact"].create.call_args
        artifact_in = args[0]
        assert artifact_in.artifact_type == "image"
        assert artifact_in.asset_id == asset_id

        # 4. Verify Job Update
        # Job should be updated with image metadata
        args, _ = repositories["job"].update.call_args_list[-1]
        update_data = args[1]
        assert update_data["output_data"]["image_url"] == "https://example.com/generated.png"
        assert update_data["output_data"]["asset_id"] == str(asset_id)


@pytest.mark.asyncio
async def test_workflow_runtime_image_reference_in_next_step(repositories):
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

    workflow_id = uuid4()
    workflow = Workflow(id=workflow_id)

    step1_id = uuid4()
    step1 = WorkflowStep(
        id=step1_id,
        name="Step1",
        step_type="ai",
        order=0,
        config={"provider": "mock", "operation": "image_generation"},
    )
    step2_id = uuid4()
    step2 = WorkflowStep(
        id=step2_id,
        name="Step2",
        step_type="ai",
        order=1,
        config={
            "provider": "mock",
            "operation": "text_generation",
            "prompt": "Analyze this image: {{Step1.image}}",
        },
    )

    repositories["step"].list_by_workflow.return_value = [step1, step2]
    repositories["execution"].create.return_value = MagicMock(id=uuid4(), status="pending")
    repositories["execution"].update.return_value = AsyncMock(id=uuid4(), status="running")
    repositories["job"].create.side_effect = [AsyncMock(id=uuid4()), AsyncMock(id=uuid4())]
    repositories["job"].update.return_value = AsyncMock()
    
    repositories["asset"].create.return_value = MagicMock(id=uuid4())
    repositories["artifact"].create.return_value = MagicMock(id=uuid4())

    # Step 1 returns image
    res1 = AIImageResponse(image_url="https://cdn.com/img.png")
    # Step 2 returns text
    res2 = MagicMock(content="Analysis", metadata={})
    res2.artifact_type = None
    res2.asset_id = None

    with (
        patch.object(runtime.validator, "validate") as mock_validate,
        patch("apps.api.ai_providers.factory.AIProviderFactory.create") as mock_factory,
    ):
        mock_validate.return_value = MagicMock(valid=True)
        mock_provider = AsyncMock()
        mock_provider.generate_image.return_value = res1
        mock_provider.generate_text.return_value = res2
        mock_factory.return_value = mock_provider

        await runtime.run(workflow)

        # Verify Step 2 received resolved image URL
        mock_provider.generate_text.assert_called_once()
        _, kwargs = mock_provider.generate_text.call_args
        assert kwargs["prompt"] == "Analyze this image: https://cdn.com/img.png"
