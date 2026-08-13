"""Runtime integration tests for the video_render operation."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from apps.api.assets.models import Asset
from apps.api.domain.models import Workflow, WorkflowArtifact, WorkflowExecution, WorkflowStep
from apps.api.storage import StoredObject
from apps.api.video_rendering import VideoRenderingError, VideoRenderResult
from apps.api.workflow.context import WorkflowContext
from apps.api.workflow.runtime import WorkflowRuntime


@pytest.fixture
def repositories() -> dict[str, AsyncMock]:
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


def _runtime(repositories, storage, renderer) -> WorkflowRuntime:
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
        video_renderer=renderer,
    )


def _execution(repositories, workflow_id):
    execution = WorkflowExecution(id=uuid4(), workflow_id=workflow_id)
    repositories["execution"].create.return_value = execution
    repositories["execution"].update.return_value = execution
    repositories["job"].create.return_value = MagicMock(id=uuid4())
    repositories["job"].update.side_effect = lambda job_id, _: MagicMock(id=job_id)
    return execution


@pytest.mark.asyncio
async def test_video_render_registers_storage_asset_artifact_then_context(repositories) -> None:
    storage, renderer = AsyncMock(), AsyncMock()
    registration_events: list[str] = []
    source_asset_id, video_asset_id, artifact_id = uuid4(), uuid4(), uuid4()
    source_asset = Asset(
        id=source_asset_id,
        object_key="generated/source.png",
        filename="source.png",
        content_type="image/png",
        size_bytes=9,
    )
    repositories["asset"].get_by_id.return_value = source_asset
    storage.download.return_value = StoredObject(body=b"image-data", content_type="image/png")
    renderer.render.return_value = VideoRenderResult(
        video_data=b"rendered-video",
        metadata={"renderer": "test", "video_codec": "h264"},
    )
    repositories["asset"].create.side_effect = lambda _: (
        registration_events.append("asset"),
        MagicMock(id=video_asset_id),
    )[1]
    repositories["artifact"].create.side_effect = lambda _: (
        registration_events.append("artifact"),
        WorkflowArtifact(id=artifact_id),
    )[1]
    storage.upload.side_effect = lambda *args, **kwargs: registration_events.append("storage")
    storage.create_presigned_download_url.return_value = "https://assets.test/video.mp4"

    workflow_id = uuid4()
    workflow = Workflow(id=workflow_id)
    step = WorkflowStep(
        id=uuid4(),
        workflow_id=workflow_id,
        name="RenderVideo",
        step_type="render",
        order=1,
        config={
            "operation": "video_render",
            "input_asset": "{{GenerateImage.asset}}",
            "duration": 4,
            "fps": 24,
            "width": 1280,
            "height": 720,
        },
    )
    repositories["step"].list_by_workflow.return_value = [step]
    execution = _execution(repositories, workflow_id)
    context = WorkflowContext()
    context.set_step_asset("GenerateImage", source_asset_id)
    original_set_step_video = context.set_step_video

    def publish_video(step_name: str, video_url: str) -> None:
        registration_events.append("context")
        original_set_step_video(step_name, video_url)

    runtime = _runtime(repositories, storage, renderer)

    with (
        patch("apps.api.workflow.runtime.WorkflowContext", return_value=context),
        patch.object(runtime.validator, "validate", return_value=MagicMock(valid=True)),
        patch.object(context, "set_step_video", side_effect=publish_video),
    ):
        result = await runtime.run(workflow)

    assert result["status"] == "completed"
    assert result["execution_id"] == execution.id
    repositories["asset"].get_by_id.assert_awaited_once_with(source_asset_id)
    storage.download.assert_awaited_once_with("generated/source.png")
    request = renderer.render.await_args.args[0]
    assert request.image_data == b"image-data"
    assert (request.duration_seconds, request.fps, request.width, request.height) == (
        4,
        24,
        1280,
        720,
    )
    storage.upload.assert_awaited_once()
    asset_create = repositories["asset"].create.await_args.args[0]
    assert asset_create.content_type == "video/mp4"
    assert asset_create.size_bytes == len(b"rendered-video")
    artifact_create = repositories["artifact"].create.await_args.args[0]
    assert artifact_create.workflow_execution_id == execution.id
    assert artifact_create.artifact_type == "video"
    assert artifact_create.asset_id == video_asset_id
    assert artifact_create.metadata_data["source_asset_id"] == str(source_asset_id)
    assert context.get_step_video("RenderVideo") == "https://assets.test/video.mp4"
    assert context.get_step_asset("RenderVideo") == video_asset_id
    assert context.get_step_artifact("RenderVideo") == artifact_id
    assert registration_events == ["storage", "asset", "artifact", "context", "context"]

    completed_job = repositories["job"].update.await_args_list[-1].args[1]
    assert completed_job["output_data"]["video_url"] == "https://assets.test/video.mp4"
    assert repositories["history"].create.await_count == 4
    assert repositories["metric"].create.await_count == 4
    repositories["error"].create.assert_not_awaited()


@pytest.mark.asyncio
async def test_video_render_failure_stops_downstream_and_does_not_publish(repositories) -> None:
    storage, renderer = AsyncMock(), AsyncMock()
    source_asset_id = uuid4()
    repositories["asset"].get_by_id.return_value = Asset(
        id=source_asset_id,
        object_key="generated/source.png",
        filename="source.png",
        content_type="image/png",
        size_bytes=9,
    )
    storage.download.return_value = StoredObject(body=b"image-data", content_type="image/png")
    renderer.render.side_effect = VideoRenderingError("render failed")

    workflow_id = uuid4()
    workflow = Workflow(id=workflow_id)
    render_step = WorkflowStep(
        id=uuid4(),
        workflow_id=workflow_id,
        name="RenderVideo",
        step_type="render",
        order=1,
        config={"operation": "video_render", "input_asset": "{{GenerateImage.asset}}"},
    )
    downstream = WorkflowStep(
        id=uuid4(),
        workflow_id=workflow_id,
        name="Downstream",
        step_type="ai",
        order=2,
        config={"operation": "text_generation", "prompt": "{{RenderVideo.video}}"},
    )
    repositories["step"].list_by_workflow.return_value = [render_step, downstream]
    execution = _execution(repositories, workflow_id)
    context = WorkflowContext()
    context.set_step_asset("GenerateImage", source_asset_id)
    runtime = _runtime(repositories, storage, renderer)

    with (
        patch("apps.api.workflow.runtime.WorkflowContext", return_value=context),
        patch.object(runtime.validator, "validate", return_value=MagicMock(valid=True)),
    ):
        result = await runtime.run(workflow)

    assert result["status"] == "failed"
    assert result["execution_id"] == execution.id
    assert "context" not in result
    assert context.get_step_video("RenderVideo") is None
    assert context.get_step_asset("RenderVideo") is None
    assert context.get_step_artifact("RenderVideo") is None
    assert repositories["job"].create.await_count == 1
    storage.upload.assert_not_awaited()
    repositories["asset"].create.assert_not_awaited()
    repositories["artifact"].create.assert_not_awaited()
    repositories["error"].create.assert_awaited_once()
    error = repositories["error"].create.await_args.args[0]
    assert error.workflow_step_id == render_step.id
    assert error.error_type == "VideoRenderingError"
    step_updates = [entry.args for entry in repositories["step"].update.await_args_list]
    assert all(entry[0] != downstream.id for entry in step_updates)
