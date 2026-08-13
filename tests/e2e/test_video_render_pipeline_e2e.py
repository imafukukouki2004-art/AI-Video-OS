"""End-to-end text, image, video-render, and downstream-reference pipeline."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from apps.api.ai_providers.base import AIImageResponse, AIResponse
from apps.api.domain.models import Workflow, WorkflowExecution, WorkflowStep
from apps.api.storage import StoredObject
from apps.api.video_rendering import VideoRenderResult
from apps.api.workflow.context import WorkflowContext
from apps.api.workflow.runtime import WorkflowRuntime


@pytest.mark.asyncio
async def test_text_image_video_storage_artifact_context_pipeline() -> None:
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
    storage, renderer = AsyncMock(), AsyncMock()
    storage.create_presigned_download_url.side_effect = [
        "https://assets.test/generated.png",
        "https://assets.test/rendered.mp4",
    ]
    storage.download.return_value = StoredObject(body=b"stored-image", content_type="image/png")
    renderer.render.return_value = VideoRenderResult(
        video_data=b"playable-mp4", metadata={"renderer": "mock", "video_codec": "h264"}
    )
    runtime = WorkflowRuntime(*repositories, storage, video_renderer=renderer)

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
                "provider": "mock",
                "operation": "text_generation",
                "prompt": "Generate a script",
            },
        ),
        WorkflowStep(
            id=uuid4(),
            workflow_id=workflow_id,
            name="GenerateImage",
            step_type="ai",
            order=2,
            config={
                "provider": "mock",
                "operation": "image_generation",
                "prompt": "Illustrate {{GenerateScript.output}}",
            },
        ),
        WorkflowStep(
            id=uuid4(),
            workflow_id=workflow_id,
            name="RenderVideo",
            step_type="render",
            order=3,
            config={
                "operation": "video_render",
                "input_asset": "{{GenerateImage.asset}}",
                "duration": 3,
                "fps": 30,
                "width": 1280,
                "height": 720,
            },
        ),
        WorkflowStep(
            id=uuid4(),
            workflow_id=workflow_id,
            name="UseVideo",
            step_type="ai",
            order=4,
            config={
                "provider": "mock",
                "operation": "text_generation",
                "prompt": "Publish {{RenderVideo.video}} with asset {{RenderVideo.asset}}",
            },
        ),
    ]
    step_repo.list_by_workflow.return_value = steps
    execution = WorkflowExecution(id=uuid4(), workflow_id=workflow_id)
    execution_repo.create.return_value = execution
    execution_repo.update.return_value = execution
    job_repo.create.side_effect = [MagicMock(id=uuid4()) for _ in steps]
    job_repo.update.side_effect = lambda job_id, _: MagicMock(id=job_id)
    image_asset_id, video_asset_id = uuid4(), uuid4()
    image_artifact_id, video_artifact_id = uuid4(), uuid4()
    asset_repo.create.side_effect = [
        MagicMock(id=image_asset_id, object_key="generated/image.png"),
        MagicMock(id=video_asset_id, object_key="rendered/video.mp4"),
    ]
    asset_repo.get_by_id.return_value = MagicMock(
        id=image_asset_id,
        object_key="generated/image.png",
        content_type="image/png",
    )
    artifact_repo.create.side_effect = [
        MagicMock(id=image_artifact_id),
        MagicMock(id=video_artifact_id),
    ]

    text_provider, image_provider, downstream_provider = AsyncMock(), AsyncMock(), AsyncMock()
    text_provider.generate_text.return_value = AIResponse(content="Launch script")
    image_provider.generate_image.return_value = AIImageResponse(
        image_bytes=b"generated-image", mime_type="image/png"
    )
    downstream_provider.generate_text.return_value = AIResponse(content="Ready to publish")
    context = WorkflowContext()

    with (
        patch("apps.api.workflow.runtime.WorkflowContext", return_value=context),
        patch(
            "apps.api.workflow.runtime.AIProviderFactory.create",
            side_effect=[text_provider, image_provider, downstream_provider],
        ),
    ):
        result = await runtime.run(workflow)

    assert result["status"] == "completed"
    image_provider.generate_image.assert_awaited_once_with(prompt="Illustrate Launch script")
    renderer.render.assert_awaited_once()
    render_request = renderer.render.await_args.args[0]
    assert render_request.image_data == b"stored-image"
    assert render_request.image_content_type == "image/png"
    downstream_provider.generate_text.assert_awaited_once_with(
        prompt=f"Publish https://assets.test/rendered.mp4 with asset {video_asset_id}"
    )
    assert storage.upload.await_count == 2
    assert asset_repo.create.await_count == 2
    assert artifact_repo.create.await_count == 2
    assert context.get_step_video("RenderVideo") == "https://assets.test/rendered.mp4"
    assert context.get_step_asset("RenderVideo") == video_asset_id
    assert context.get_step_artifact("RenderVideo") == video_artifact_id
    assert context.get_step_output("UseVideo") == "Ready to publish"
    assert history_repo.create.await_count == 10
    assert metric_repo.create.await_count == 4
    error_repo.create.assert_not_awaited()
