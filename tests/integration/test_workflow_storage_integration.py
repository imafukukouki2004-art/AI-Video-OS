"""Integration tests for Workflow Generated Asset Storage."""

from unittest.mock import AsyncMock, patch
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
def mock_storage():
    return AsyncMock()


@pytest.fixture
def runtime(mock_repos, mock_storage):
    with patch("apps.api.workflow.runtime.ImageRetriever") as mock_retriever_cls:
        mock_retriever = mock_retriever_cls.return_value
        mock_retriever.retrieve = AsyncMock(return_value=b"fake-image-bytes")
        mock_retriever.get_extension.return_value = ".png"

        rt = WorkflowRuntime(
            mock_repos["job"],
            mock_repos["execution"],
            mock_repos["step"],
            mock_repos["history"],
            mock_repos["error"],
            mock_repos["metric"],
            mock_repos["artifact"],
            mock_repos["asset"],
            mock_storage,
        )
        # Attach mock retriever to runtime for verification
        rt.retriever = mock_retriever
        return rt


@pytest.mark.asyncio
async def test_workflow_runtime_image_generation_with_storage(runtime, mock_repos, mock_storage):
    workflow_id = uuid4()
    execution_id = uuid4()
    step_id = uuid4()
    image_url = "https://example.com/generated.png"
    image_data = b"fake-image-bytes"

    workflow = Workflow(id=workflow_id)
    step = WorkflowStep(
        id=step_id,
        workflow_id=workflow_id,
        name="gen_img",
        step_type="ai",
        order=0,
        config={"provider": "mock", "operation": "image_generation", "prompt": "a sunset"},
    )

    execution = WorkflowExecution(
        id=execution_id, workflow_id=workflow_id, status=WorkflowExecutionStatus.PENDING
    )

    mock_repos["step"].list_by_workflow.return_value = [step]
    mock_repos["execution"].get_by_id.return_value = execution
    mock_repos["execution"].update.return_value = execution
    mock_repos["job"].create.return_value = AsyncMock(id=uuid4())
    mock_repos["job"].update.return_value = AsyncMock()
    mock_repos["artifact"].create.return_value = AsyncMock(id=uuid4())
    mock_repos["asset"].create.return_value = AsyncMock(id=uuid4())
    mock_storage.create_presigned_download_url.return_value = "https://minio.local/presigned-url"

    # Mock AI Provider to return image URL
    mock_ai_res = AIImageResponse(
        image_url=image_url,
        raw_response={},
        metadata={"model": "dall-e-3"},
    )

    with patch("apps.api.ai_providers.factory.AIProviderFactory.create") as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.generate_image.return_value = mock_ai_res
        mock_factory.return_value = mock_provider

        await runtime.run(workflow, execution_id=execution_id)

        # 1. Verify Image Retrieval
        runtime.retriever.retrieve.assert_called_once_with(image_url)

        # 2. Verify Storage Upload
        mock_storage.upload.assert_called_once()
        _, kwargs = mock_storage.upload.call_args
        assert kwargs["body"] == image_data
        assert kwargs["content_type"] == "image/png"
        assert kwargs["key"].startswith(f"generated/{execution_id}/{step_id}/")

        # 3. Verify Asset Registration
        mock_repos["asset"].create.assert_called_once()
        asset_in = mock_repos["asset"].create.call_args[0][0]
        assert asset_in.size_bytes == len(image_data)
        assert asset_in.content_type == "image/png"

        # 4. Verify Artifact Registration
        mock_repos["artifact"].create.assert_called_once()

        # 5. Verify Presigned URL creation
        mock_storage.create_presigned_download_url.assert_called_once()
