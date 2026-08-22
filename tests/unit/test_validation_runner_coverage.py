import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from apps.api.publishing.models import PublicationStatus
from apps.api.publishing.repository import PublicationRepository
from apps.api.repositories.sqlalchemy import (
    AssetRepository,
    WorkflowArtifactRepository,
    WorkflowRepository,
    WorkflowStepRepository,
)
from apps.api.services.validation_runner import ValidationRunner
from apps.api.services.workflow_runtime import WorkflowRuntimeService
from apps.api.storage import ObjectStorage


@pytest.fixture
def mock_deps():
    return {
        "workflow_runtime_service": MagicMock(spec=WorkflowRuntimeService),
        "workflow_repository": MagicMock(spec=WorkflowRepository),
        "step_repository": MagicMock(spec=WorkflowStepRepository),
        "artifact_repository": MagicMock(spec=WorkflowArtifactRepository),
        "asset_repository": MagicMock(spec=AssetRepository),
        "publication_repository": MagicMock(spec=PublicationRepository),
        "storage": MagicMock(spec=ObjectStorage),
    }


@pytest.mark.asyncio
async def test_validation_runner_workflow_failure(mock_deps):
    with patch.dict(os.environ, {"AI_VIDEO_OS_RUN_PRODUCTION_E2E": "true"}):
        runner = ValidationRunner(**mock_deps)

        mock_workflow = MagicMock(id=uuid4())
        mock_deps["workflow_repository"].create = AsyncMock(return_value=mock_workflow)
        mock_deps["step_repository"].create = AsyncMock()
        mock_deps["workflow_runtime_service"].execute_workflow = AsyncMock(
            return_value={
                "status": "failed",
                "error": "Runtime failed",
                "execution_id": uuid4(),
            }
        )

        result = await runner.run_production_e2e({})
        assert result["validation_result"] == "FAILED"
        assert result["error"] == "Runtime failed"


@pytest.mark.asyncio
async def test_validation_runner_invalid_execution_id(mock_deps):
    with patch.dict(os.environ, {"AI_VIDEO_OS_RUN_PRODUCTION_E2E": "true"}):
        runner = ValidationRunner(**mock_deps)

        mock_workflow = MagicMock(id=uuid4())
        mock_deps["workflow_repository"].create = AsyncMock(return_value=mock_workflow)
        mock_deps["step_repository"].create = AsyncMock()
        mock_deps["workflow_runtime_service"].execute_workflow = AsyncMock(
            return_value={
                "status": "completed",
                "execution_id": "not-a-uuid",
            }
        )

        result = await runner.run_production_e2e({})
        assert result["validation_result"] == "FAILED"
        assert "Invalid execution ID" in result["error"]


@pytest.mark.asyncio
async def test_validation_runner_video_asset_not_found(mock_deps):
    with patch.dict(os.environ, {"AI_VIDEO_OS_RUN_PRODUCTION_E2E": "true"}):
        runner = ValidationRunner(**mock_deps)

        mock_workflow = MagicMock(id=uuid4())
        mock_deps["workflow_repository"].create = AsyncMock(return_value=mock_workflow)
        mock_deps["step_repository"].create = AsyncMock()
        execution_id = uuid4()
        mock_deps["workflow_runtime_service"].execute_workflow = AsyncMock(
            return_value={
                "status": "completed",
                "execution_id": execution_id,
            }
        )

        with patch.object(runner, "_get_video_asset_id", return_value=None):
            result = await runner.run_production_e2e({})
            assert result["validation_result"] == "FAILED"
            assert "Video asset not found" in result["error"]


@pytest.mark.asyncio
async def test_validation_runner_visual_validation_fails(mock_deps):
    with patch.dict(os.environ, {"AI_VIDEO_OS_RUN_PRODUCTION_E2E": "true"}):
        runner = ValidationRunner(**mock_deps)

        mock_workflow = MagicMock(id=uuid4())
        mock_deps["workflow_repository"].create = AsyncMock(return_value=mock_workflow)
        mock_deps["step_repository"].create = AsyncMock()
        execution_id = uuid4()
        mock_deps["workflow_runtime_service"].execute_workflow = AsyncMock(
            return_value={
                "status": "completed",
                "execution_id": execution_id,
            }
        )

        with patch.object(runner, "_get_video_asset_id", return_value=uuid4()):
            with patch.object(
                runner,
                "_perform_visual_validation",
                return_value={"valid": False, "reason": "Black frames detected"},
            ):
                result = await runner.run_production_e2e({})
                assert result["validation_result"] == "FAILED"
                assert result["visual_validation"]["reason"] == "Black frames detected"


@pytest.mark.asyncio
async def test_validation_runner_publication_not_found(mock_deps):
    with patch.dict(os.environ, {"AI_VIDEO_OS_RUN_PRODUCTION_E2E": "true"}):
        runner = ValidationRunner(**mock_deps)

        mock_workflow = MagicMock(id=uuid4())
        mock_deps["workflow_repository"].create = AsyncMock(return_value=mock_workflow)
        mock_deps["step_repository"].create = AsyncMock()
        execution_id = uuid4()
        mock_deps["workflow_runtime_service"].execute_workflow = AsyncMock(
            return_value={
                "status": "completed",
                "execution_id": execution_id,
            }
        )

        with patch.object(runner, "_get_video_asset_id", return_value=uuid4()):
            with patch.object(
                runner,
                "_perform_visual_validation",
                return_value={"valid": True, "reason": "Valid"},
            ):
                mock_deps["publication_repository"].list_by_execution = AsyncMock(return_value=[])

                result = await runner.run_production_e2e({})
                assert result["validation_result"] == "FAILED"
                assert "Publication record not found" in result["error"]


@pytest.mark.asyncio
async def test_validation_runner_publication_failed_status(mock_deps):
    with patch.dict(os.environ, {"AI_VIDEO_OS_RUN_PRODUCTION_E2E": "true"}):
        runner = ValidationRunner(**mock_deps)

        mock_workflow = MagicMock(id=uuid4())
        mock_deps["workflow_repository"].create = AsyncMock(return_value=mock_workflow)
        mock_deps["step_repository"].create = AsyncMock()
        execution_id = uuid4()
        mock_deps["workflow_runtime_service"].execute_workflow = AsyncMock(
            return_value={
                "status": "completed",
                "execution_id": execution_id,
            }
        )

        with patch.object(runner, "_get_video_asset_id", return_value=uuid4()):
            with patch.object(
                runner,
                "_perform_visual_validation",
                return_value={"valid": True, "reason": "Valid"},
            ):
                mock_pub = MagicMock()
                mock_pub.id = uuid4()
                mock_pub.status = PublicationStatus.FAILED
                mock_pub.error_message = "YouTube API quota exceeded"
                mock_deps["publication_repository"].list_by_execution = AsyncMock(
                    return_value=[mock_pub]
                )

                with patch(
                    "apps.api.services.validation_runner.asyncio.sleep",
                    new_callable=AsyncMock,
                ):
                    result = await runner.run_production_e2e({})
                    assert result["validation_result"] == "FAILED"
                    assert "YouTube API quota exceeded" in result["error"]


@pytest.mark.asyncio
async def test_validation_runner_exception_handling(mock_deps):
    with patch.dict(os.environ, {"AI_VIDEO_OS_RUN_PRODUCTION_E2E": "true"}):
        runner = ValidationRunner(**mock_deps)
        mock_deps["workflow_repository"].create = AsyncMock(
            side_effect=Exception("DB Connection Error")
        )

        result = await runner.run_production_e2e({})
        assert result["validation_result"] == "FAILED"
        assert "DB Connection Error" in result["error"]
