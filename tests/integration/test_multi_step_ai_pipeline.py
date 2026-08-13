"""Integration coverage for sequential multi-step AI pipelines."""

from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import uuid4

import pytest

from apps.api.ai_providers.base import AIImageResponse, AIResponse
from apps.api.domain.models import (
    JobStatus,
    Workflow,
    WorkflowExecution,
    WorkflowExecutionStatus,
    WorkflowStep,
    WorkflowStepStatus,
)
from apps.api.workflow.context import WorkflowContext
from apps.api.workflow.runtime import WorkflowRuntime


def _repositories() -> dict[str, AsyncMock]:
    return {
        name: AsyncMock()
        for name in (
            "job",
            "execution",
            "step",
            "history",
            "error",
            "metric",
            "artifact",
            "asset",
        )
    }


def _steps(workflow_id):
    return [
        WorkflowStep(
            id=uuid4(),
            workflow_id=workflow_id,
            name="GenerateScript",
            step_type="ai",
            order=1,
            config={
                "provider": "mock",
                "operation": "text_generation",
                "system_prompt": "Write production-ready scripts.",
                "prompt": "Generate a launch script",
            },
        ),
        WorkflowStep(
            id=uuid4(),
            workflow_id=workflow_id,
            name="RewriteScript",
            step_type="ai",
            order=2,
            config={
                "provider": "mock",
                "operation": "text_generation",
                "prompt": "Rewrite: {{GenerateScript.output}}",
            },
        ),
        WorkflowStep(
            id=uuid4(),
            workflow_id=workflow_id,
            name="GenerateImage",
            step_type="ai",
            order=3,
            config={
                "provider": "mock",
                "operation": "image_generation",
                "prompt": "Key visual for {{RewriteScript.output}}",
                "size": "1024x1024",
            },
        ),
    ]


def _runtime(repositories, storage) -> WorkflowRuntime:
    return WorkflowRuntime(
        repositories["job"],
        repositories["execution"],
        repositories["step"],
        repositories["history"],
        repositories["error"],
        repositories["metric"],
        repositories["artifact"],
        repositories["asset"],
        storage,
    )


def _configure_execution(repositories, workflow_id):
    execution = WorkflowExecution(
        id=uuid4(), workflow_id=workflow_id, status=WorkflowExecutionStatus.PENDING
    )
    repositories["execution"].create.return_value = execution
    repositories["execution"].update.return_value = execution
    repositories["job"].create.side_effect = [
        MagicMock(id=uuid4()),
        MagicMock(id=uuid4()),
        MagicMock(id=uuid4()),
    ]
    repositories["job"].update.side_effect = lambda job_id, _: MagicMock(id=job_id)
    return execution


@pytest.mark.asyncio
async def test_text_text_image_pipeline_handoff_and_observability() -> None:
    repositories = _repositories()
    storage = AsyncMock()
    storage.create_presigned_download_url.return_value = "https://assets.test/key-visual.png"
    workflow_id = uuid4()
    workflow = Workflow(id=workflow_id)
    steps = _steps(workflow_id)
    repositories["step"].list_by_workflow.return_value = steps
    execution = _configure_execution(repositories, workflow_id)
    asset_id, artifact_id = uuid4(), uuid4()
    repositories["asset"].create.return_value = MagicMock(id=asset_id)
    repositories["artifact"].create.return_value = MagicMock(id=artifact_id)
    runtime = _runtime(repositories, storage)
    runtime.retriever.get_extension = MagicMock(return_value=".png")

    script_provider = AsyncMock()
    script_provider.generate_text.return_value = AIResponse(content="Original script")
    rewrite_provider = AsyncMock()
    rewrite_provider.generate_text.return_value = AIResponse(content="Rewritten script")
    image_provider = AsyncMock()
    image_provider.generate_image.return_value = AIImageResponse(
        image_bytes=b"pipeline-image", metadata={"provider": "mock"}
    )
    context = WorkflowContext()

    with (
        patch("apps.api.workflow.runtime.WorkflowContext", return_value=context),
        patch(
            "apps.api.workflow.runtime.AIProviderFactory.create",
            side_effect=[script_provider, rewrite_provider, image_provider],
        ) as provider_factory,
    ):
        result = await runtime.run(workflow)

    assert result["status"] == "completed"
    assert result["execution_id"] == execution.id
    provider_factory.assert_has_calls([call("mock"), call("mock"), call("mock")])
    script_provider.generate_text.assert_awaited_once_with(
        prompt="Generate a launch script",
        system_prompt="Write production-ready scripts.",
    )
    rewrite_provider.generate_text.assert_awaited_once_with(prompt="Rewrite: Original script")
    image_provider.generate_image.assert_awaited_once_with(
        prompt="Key visual for Rewritten script", size="1024x1024"
    )
    storage.upload.assert_awaited_once()
    repositories["asset"].create.assert_awaited_once()
    repositories["artifact"].create.assert_awaited_once()
    assert context.get_step_output("GenerateScript") == "Original script"
    assert context.get_step_output("RewriteScript") == "Rewritten script"
    assert context.get_step_image("GenerateImage") == "https://assets.test/key-visual.png"
    assert context.get_step_asset("GenerateImage") == asset_id
    assert context.get_step_artifact("GenerateImage") == artifact_id

    step_updates = [entry.args for entry in repositories["step"].update.await_args_list]
    assert step_updates == [
        (steps[0].id, {"status": WorkflowStepStatus.RUNNING}),
        (steps[0].id, {"status": WorkflowStepStatus.COMPLETED}),
        (steps[1].id, {"status": WorkflowStepStatus.RUNNING}),
        (steps[1].id, {"status": WorkflowStepStatus.COMPLETED}),
        (steps[2].id, {"status": WorkflowStepStatus.RUNNING}),
        (steps[2].id, {"status": WorkflowStepStatus.COMPLETED}),
    ]
    assert repositories["history"].create.await_count == 8
    assert repositories["metric"].create.await_count == 4
    metric_values = {
        metric.args[0].metric_type: metric.args[0].metric_value
        for metric in repositories["metric"].create.await_args_list
    }
    assert metric_values["step_count"] == 3
    assert metric_values["success_count"] == 3
    assert metric_values["failure_count"] == 0
    repositories["error"].create.assert_not_awaited()


@pytest.mark.asyncio
async def test_pipeline_failure_stops_downstream_and_does_not_publish_context() -> None:
    repositories = _repositories()
    workflow_id = uuid4()
    workflow = Workflow(id=workflow_id)
    steps = _steps(workflow_id)
    repositories["step"].list_by_workflow.return_value = steps
    execution = _configure_execution(repositories, workflow_id)
    runtime = _runtime(repositories, AsyncMock())

    first_provider = AsyncMock()
    first_provider.generate_text.return_value = AIResponse(content="Original script")
    failed_provider = AsyncMock()
    failed_provider.generate_text.side_effect = RuntimeError("provider failed")
    context = WorkflowContext()

    with (
        patch("apps.api.workflow.runtime.WorkflowContext", return_value=context),
        patch(
            "apps.api.workflow.runtime.AIProviderFactory.create",
            side_effect=[first_provider, failed_provider],
        ) as provider_factory,
    ):
        result = await runtime.run(workflow)

    assert result == {
        "status": "failed",
        "error": "provider failed",
        "execution_id": execution.id,
    }
    assert "context" not in result
    assert "outputs" not in result
    assert context.get_step_output("GenerateScript") == "Original script"
    assert context.get_step_output("RewriteScript") is None
    assert context.get_step_output("GenerateImage") is None
    assert provider_factory.call_count == 2
    assert repositories["job"].create.await_count == 2
    assert repositories["asset"].create.await_count == 0
    assert repositories["artifact"].create.await_count == 0

    step_updates = [entry.args for entry in repositories["step"].update.await_args_list]
    assert step_updates[-1] == (steps[1].id, {"status": WorkflowStepStatus.FAILED})
    assert all(entry[0] != steps[2].id for entry in step_updates)
    job_updates = [entry.args[1] for entry in repositories["job"].update.await_args_list]
    assert job_updates[-1] == {"status": JobStatus.FAILED}
    execution_updates = [
        entry.args[1] for entry in repositories["execution"].update.await_args_list
    ]
    assert execution_updates[-1]["status"] == WorkflowExecutionStatus.FAILED
    repositories["error"].create.assert_awaited_once()
    error = repositories["error"].create.await_args.args[0]
    assert error.workflow_step_id == steps[1].id
    assert error.error_message == "provider failed"
    assert repositories["history"].create.await_count == 5
    metric_values = {
        metric.args[0].metric_type: metric.args[0].metric_value
        for metric in repositories["metric"].create.await_args_list
    }
    assert metric_values["step_count"] == 1
    assert metric_values["success_count"] == 1
    assert metric_values["failure_count"] == 1
