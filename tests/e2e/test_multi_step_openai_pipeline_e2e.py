"""End-to-end runtime pipeline with the OpenAI SDK boundary mocked."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from apps.api.ai_providers.openai import OpenAIProvider
from apps.api.domain.models import (
    Workflow,
    WorkflowExecution,
    WorkflowExecutionStatus,
    WorkflowStep,
)
from apps.api.workflow.context import WorkflowContext
from apps.api.workflow.runtime import WorkflowRuntime


@pytest.mark.asyncio
async def test_openai_text_text_image_pipeline_reaches_storage_and_context() -> None:
    repositories = [AsyncMock() for _ in range(8)]
    (
        job_repo,
        execution_repo,
        step_repo,
        history_repo,
        error_repo,
        metric_repo,
        artifact_repo,
        asset_repo,
    ) = repositories
    storage = AsyncMock()
    storage.create_presigned_download_url.return_value = "https://assets.test/openai-image.png"
    runtime = WorkflowRuntime(*repositories, storage)
    runtime.retriever.retrieve = AsyncMock(return_value=b"openai-image")
    runtime.retriever.get_extension = MagicMock(return_value=".png")

    workflow_id = uuid4()
    workflow = Workflow(id=workflow_id)
    steps = [
        WorkflowStep(
            id=uuid4(),
            workflow_id=workflow_id,
            name="GenerateScript",
            step_type="ai",
            order=1,
            config={
                "provider": "openai",
                "operation": "text_generation",
                "prompt": "Generate a script",
            },
        ),
        WorkflowStep(
            id=uuid4(),
            workflow_id=workflow_id,
            name="RewriteScript",
            step_type="ai",
            order=2,
            config={
                "provider": "openai",
                "operation": "text_generation",
                "prompt": "Rewrite {{GenerateScript.output}}",
            },
        ),
        WorkflowStep(
            id=uuid4(),
            workflow_id=workflow_id,
            name="GenerateImage",
            step_type="ai",
            order=3,
            config={
                "provider": "openai",
                "operation": "image_generation",
                "prompt": "Illustrate {{RewriteScript.output}}",
            },
        ),
    ]
    step_repo.list_by_workflow.return_value = steps
    execution = WorkflowExecution(
        id=uuid4(), workflow_id=workflow_id, status=WorkflowExecutionStatus.PENDING
    )
    execution_repo.create.return_value = execution
    execution_repo.update.return_value = execution
    job_repo.create.side_effect = [MagicMock(id=uuid4()) for _ in steps]
    job_repo.update.side_effect = lambda job_id, _: MagicMock(id=job_id)
    asset_id, artifact_id = uuid4(), uuid4()
    asset_repo.create.return_value = MagicMock(id=asset_id)
    artifact_repo.create.return_value = MagicMock(id=artifact_id)

    text_provider = OpenAIProvider(api_key="test-key")
    text_provider.client = MagicMock()
    first_response = MagicMock(usage=None)
    first_response.choices = [MagicMock(message=MagicMock(content="Original script"))]
    second_response = MagicMock(usage=None)
    second_response.choices = [MagicMock(message=MagicMock(content="Rewritten script"))]
    text_provider.client.chat.completions.create = AsyncMock(
        side_effect=[first_response, second_response]
    )

    image_provider = OpenAIProvider(api_key="test-key")
    image_provider.client = MagicMock()
    image_response = MagicMock()
    image_response.data = [
        MagicMock(url="https://provider.test/image.png", b64_json=None, revised_prompt=None)
    ]
    image_provider.client.images.generate = AsyncMock(return_value=image_response)
    context = WorkflowContext()

    with (
        patch("apps.api.workflow.runtime.WorkflowContext", return_value=context),
        patch(
            "apps.api.workflow.runtime.AIProviderFactory.create",
            side_effect=[text_provider, text_provider, image_provider],
        ),
    ):
        result = await runtime.run(workflow)

    assert result["status"] == "completed"
    text_calls = text_provider.client.chat.completions.create.await_args_list
    assert text_calls[0].kwargs["messages"][-1] == {
        "role": "user",
        "content": "Generate a script",
    }
    assert text_calls[1].kwargs["messages"][-1] == {
        "role": "user",
        "content": "Rewrite Original script",
    }
    image_provider.client.images.generate.assert_awaited_once()
    image_call = image_provider.client.images.generate.await_args.kwargs
    assert image_call["prompt"] == "Illustrate Rewritten script"
    storage.upload.assert_awaited_once()
    artifact_repo.create.assert_awaited_once()
    asset_repo.create.assert_awaited_once()
    assert context.get_step_output("GenerateScript") == "Original script"
    assert context.get_step_output("RewriteScript") == "Rewritten script"
    assert context.get_step_image("GenerateImage") == "https://assets.test/openai-image.png"
    assert context.get_step_asset("GenerateImage") == asset_id
    assert context.get_step_artifact("GenerateImage") == artifact_id
    error_repo.create.assert_not_awaited()
    assert history_repo.create.await_count == 8
    assert metric_repo.create.await_count == 4
