"""Runtime MVP acceptance tests for the production enqueue and worker path."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from apps.api.ai_providers.base import AIImageResponse, AIResponse
from apps.api.application import create_app
from apps.api.assets.models import Asset
from apps.api.dependencies import get_workflow_queue_service
from apps.api.domain.models import (
    Job,
    JobStatus,
    Workflow,
    WorkflowArtifact,
    WorkflowExecution,
    WorkflowExecutionStatus,
    WorkflowStep,
)
from apps.api.services.workflow_queue import WorkflowQueueService
from apps.api.storage import StoredObject
from apps.api.video_rendering import VideoRenderingError, VideoRenderResult
from apps.api.workflow.context import WorkflowContext
from apps.api.workflow.runtime import WorkflowRuntime
from apps.worker.tasks import _execute_workflow_execution_async


def _runtime_mvp_steps(workflow_id: UUID) -> list[WorkflowStep]:
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
                "system_prompt": "Write concise social video scripts.",
                "prompt": "Create a three-scene launch script.",
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
                "prompt": "Create the hero frame for {{GenerateScript.output}}",
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
    ]


@pytest.mark.asyncio
async def test_api_enqueue_worker_completes_runtime_mvp() -> None:
    workflow_id, execution_id = uuid4(), uuid4()
    workflow = Workflow(id=workflow_id, workflow_type="ai_video_runtime_mvp")
    steps = _runtime_mvp_steps(workflow_id)
    execution = WorkflowExecution(
        id=execution_id,
        workflow_id=workflow_id,
        status=WorkflowExecutionStatus.PENDING,
    )

    workflow_repo, execution_repo, step_repo, job_repo = (
        AsyncMock(),
        AsyncMock(),
        AsyncMock(),
        AsyncMock(),
    )
    history_repo, error_repo, metric_repo = AsyncMock(), AsyncMock(), AsyncMock()
    artifact_repo, asset_repo, storage, renderer = (
        AsyncMock(),
        AsyncMock(),
        AsyncMock(),
        AsyncMock(),
    )
    workflow_repo.get_by_id.return_value = workflow
    execution_repo.create.return_value = execution
    execution_repo.get_by_id.return_value = execution

    async def update_execution(_: UUID, values: dict) -> WorkflowExecution:
        for key, value in values.items():
            setattr(execution, key, value)
        return execution

    execution_repo.update.side_effect = update_execution
    step_repo.list_by_workflow.return_value = steps

    jobs = [
        Job(
            id=uuid4(),
            workflow_id=workflow_id,
            step_id=step.id,
            execution_id=execution_id,
            name=step.name,
            status=JobStatus.PENDING,
            input_data=step.config,
        )
        for step in steps
    ]
    job_repo.create.side_effect = jobs
    jobs_by_id = {job.id: job for job in jobs}

    async def update_job(job_id: UUID, values: dict) -> Job:
        job = jobs_by_id[job_id]
        for key, value in values.items():
            setattr(job, key, value)
        return job

    job_repo.update.side_effect = update_job

    stored_assets: list[Asset] = []

    async def create_asset(asset_in) -> Asset:
        asset = Asset(
            id=uuid4(),
            object_key=asset_in.object_key,
            filename=asset_in.filename,
            content_type=asset_in.content_type,
            size_bytes=asset_in.size_bytes,
            created_at=datetime.now(UTC),
        )
        stored_assets.append(asset)
        return asset

    async def get_asset(asset_id: UUID) -> Asset | None:
        return next((asset for asset in stored_assets if asset.id == asset_id), None)

    asset_repo.create.side_effect = create_asset
    asset_repo.get_by_id.side_effect = get_asset

    stored_artifacts: list[WorkflowArtifact] = []

    async def create_artifact(artifact_in) -> WorkflowArtifact:
        artifact = WorkflowArtifact(
            id=uuid4(),
            workflow_execution_id=artifact_in.workflow_execution_id,
            workflow_step_id=artifact_in.workflow_step_id,
            artifact_type=artifact_in.artifact_type,
            asset_id=artifact_in.asset_id,
            metadata_data=artifact_in.metadata_data,
            created_at=datetime.now(UTC),
        )
        stored_artifacts.append(artifact)
        return artifact

    artifact_repo.create.side_effect = create_artifact
    objects: dict[str, StoredObject] = {}

    async def upload(key: str, body: bytes, content_type: str) -> None:
        objects[key] = StoredObject(body=body, content_type=content_type)

    async def download(key: str) -> StoredObject:
        return objects[key]

    async def presign(key: str, expires_in: int) -> str:
        assert expires_in == 3600
        return f"https://assets.test/{key}"

    storage.upload.side_effect = upload
    storage.download.side_effect = download
    storage.create_presigned_download_url.side_effect = presign
    storage.close = AsyncMock()

    text_provider, image_provider = AsyncMock(), AsyncMock()
    text_provider.generate_text.return_value = AIResponse(content="Launch in three vivid scenes")
    image_provider.generate_image.return_value = AIImageResponse(
        image_bytes=b"runtime-mvp-image",
        mime_type="image/png",
        metadata={"provider": "mock"},
    )
    renderer.render.return_value = VideoRenderResult(
        video_data=b"runtime-mvp-mp4",
        metadata={"renderer": "mock", "video_codec": "h264"},
    )
    context = WorkflowContext()

    queue_service = WorkflowQueueService(execution_repo)
    app: FastAPI = create_app()
    app.dependency_overrides[get_workflow_queue_service] = lambda: queue_service
    task = MagicMock(id="runtime-mvp-task")

    database = MagicMock()
    database.session_factory.return_value.__aenter__.return_value = AsyncMock()
    database.session_factory.return_value.__aexit__.return_value = None
    database.dispose = AsyncMock()

    with (
        patch("apps.api.services.workflow_queue.celery_app.send_task", return_value=task),
        patch("apps.worker.tasks.Database", return_value=database),
        patch("apps.worker.tasks.S3ObjectStorage", return_value=storage),
        patch("apps.worker.tasks.WorkflowRepository", return_value=workflow_repo),
        patch("apps.worker.tasks.WorkflowExecutionRepository", return_value=execution_repo),
        patch("apps.worker.tasks.WorkflowStepRepository", return_value=step_repo),
        patch("apps.worker.tasks.JobRepository", return_value=job_repo),
        patch("apps.worker.tasks.WorkflowExecutionHistoryRepository", return_value=history_repo),
        patch("apps.worker.tasks.WorkflowExecutionErrorRepository", return_value=error_repo),
        patch("apps.worker.tasks.WorkflowExecutionMetricRepository", return_value=metric_repo),
        patch("apps.worker.tasks.WorkflowArtifactRepository", return_value=artifact_repo),
        patch("apps.worker.tasks.AssetRepository", return_value=asset_repo),
        patch("apps.worker.tasks.FFmpegVideoRenderer", return_value=renderer),
        patch("apps.api.workflow.runtime.WorkflowContext", return_value=context),
        patch(
            "apps.api.workflow.runtime.AIProviderFactory.create",
            side_effect=[text_provider, image_provider],
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            enqueue_response = await client.post(f"/workflows/{workflow_id}/enqueue")
        worker_result = await _execute_workflow_execution_async(str(execution_id))

    assert enqueue_response.status_code == 202
    assert enqueue_response.json() == {
        "execution_id": str(execution_id),
        "task_id": "runtime-mvp-task",
        "status": "QUEUED",
    }
    assert worker_result["status"] == "completed"
    assert worker_result["execution_id"] == execution_id
    assert execution.status == WorkflowExecutionStatus.COMPLETED
    assert all(job.status == JobStatus.COMPLETED for job in jobs)
    image_provider.generate_image.assert_awaited_once_with(
        prompt="Create the hero frame for Launch in three vivid scenes"
    )
    renderer.render.assert_awaited_once()
    assert renderer.render.await_args.args[0].image_data == b"runtime-mvp-image"

    assert [asset.content_type for asset in stored_assets] == ["image/png", "video/mp4"]
    assert [artifact.artifact_type for artifact in stored_artifacts] == ["image", "video"]
    assert all(artifact.workflow_execution_id == execution_id for artifact in stored_artifacts)
    final_artifact = stored_artifacts[-1]
    assert final_artifact.asset_id == stored_assets[-1].id
    assert context.get_step_video("RenderVideo") is not None
    assert context.get_step_asset("RenderVideo") == stored_assets[-1].id
    assert context.get_step_artifact("RenderVideo") == final_artifact.id
    assert history_repo.create.await_count == 8
    assert metric_repo.create.await_count == 4
    error_repo.create.assert_not_awaited()
    storage.close.assert_awaited_once()
    database.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_runtime_mvp_video_failure_stops_and_keeps_video_context_unpublished() -> None:
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
    runtime = WorkflowRuntime(*repositories, storage, video_renderer=renderer)
    workflow_id, execution_id = uuid4(), uuid4()
    workflow = Workflow(id=workflow_id, workflow_type="ai_video_runtime_mvp")
    steps = _runtime_mvp_steps(workflow_id)
    downstream = WorkflowStep(
        id=uuid4(),
        workflow_id=workflow_id,
        name="MustNotRun",
        step_type="ai",
        order=4,
        config={
            "provider": "mock",
            "operation": "text_generation",
            "prompt": "Use {{RenderVideo.video}}",
        },
    )
    step_repo.list_by_workflow.return_value = [*steps, downstream]
    execution = WorkflowExecution(
        id=execution_id,
        workflow_id=workflow_id,
        status=WorkflowExecutionStatus.PENDING,
    )
    execution_repo.create.return_value = execution
    execution_repo.update.return_value = execution
    job_repo.create.side_effect = [MagicMock(id=uuid4()) for _ in range(3)]
    job_repo.update.side_effect = lambda job_id, _: MagicMock(id=job_id)
    image_asset_id = uuid4()
    asset_repo.create.return_value = MagicMock(id=image_asset_id)
    asset_repo.get_by_id.return_value = Asset(
        id=image_asset_id,
        object_key="generated/image.png",
        filename="image.png",
        content_type="image/png",
        size_bytes=5,
    )
    artifact_repo.create.return_value = WorkflowArtifact(id=uuid4())
    storage.download.return_value = StoredObject(body=b"image", content_type="image/png")
    storage.create_presigned_download_url.return_value = "https://assets.test/image.png"
    renderer.render.side_effect = VideoRenderingError("render failed")
    text_provider, image_provider = AsyncMock(), AsyncMock()
    text_provider.generate_text.return_value = AIResponse(content="Launch script")
    image_provider.generate_image.return_value = AIImageResponse(
        image_bytes=b"image", mime_type="image/png"
    )
    context = WorkflowContext()

    with (
        patch("apps.api.workflow.runtime.WorkflowContext", return_value=context),
        patch(
            "apps.api.workflow.runtime.AIProviderFactory.create",
            side_effect=[text_provider, image_provider],
        ),
    ):
        result = await runtime.run(workflow)

    assert result["status"] == "failed"
    assert result["execution_id"] == execution_id
    assert context.get_step_image("GenerateImage") == "https://assets.test/image.png"
    assert context.get_step_video("RenderVideo") is None
    assert context.get_step_asset("RenderVideo") is None
    assert context.get_step_artifact("RenderVideo") is None
    assert job_repo.create.await_count == 3
    assert artifact_repo.create.await_count == 1
    assert error_repo.create.await_count == 1
    assert error_repo.create.await_args.args[0].workflow_step_id == steps[2].id
    assert execution_repo.update.await_args_list[-1].args[1]["status"] == (
        WorkflowExecutionStatus.FAILED
    )
    assert all(call.args[0] != downstream.id for call in step_repo.update.await_args_list)
    assert history_repo.create.await_count == 7
    assert metric_repo.create.await_count == 4
