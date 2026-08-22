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
async def test_validation_runner_skips_without_opt_in(mock_deps):
    with patch.dict(os.environ, {"AI_VIDEO_OS_RUN_PRODUCTION_E2E": "false"}):
        runner = ValidationRunner(**mock_deps)
        result = await runner.run_production_e2e({})
        assert result["status"] == "skipped"
        assert "Explicit opt-in required" in result["reason"]


@pytest.mark.asyncio
async def test_validation_runner_enforces_private_status(mock_deps):
    with patch.dict(os.environ, {"AI_VIDEO_OS_RUN_PRODUCTION_E2E": "true"}):
        runner = ValidationRunner(**mock_deps)

        workflow_id = uuid4()
        mock_workflow = MagicMock(id=workflow_id)
        mock_deps["workflow_repository"].create = AsyncMock(return_value=mock_workflow)
        mock_deps["step_repository"].create = AsyncMock()

        await runner._setup_validation_workflow({})

        args, _ = mock_deps["workflow_repository"].create.call_args
        workflow_in = args[0]
        assert workflow_in.config["publishing_config"]["privacyStatus"] == "private"


@pytest.mark.asyncio
async def test_validation_runner_rejects_non_private(mock_deps):
    with patch.dict(os.environ, {"AI_VIDEO_OS_RUN_PRODUCTION_E2E": "true"}):
        runner = ValidationRunner(**mock_deps)

        mock_workflow = MagicMock(id=uuid4())
        mock_deps["workflow_repository"].create = AsyncMock(return_value=mock_workflow)
        mock_deps["step_repository"].create = AsyncMock()
        mock_deps["workflow_runtime_service"].execute_workflow = AsyncMock(
            return_value={"status": "completed", "execution_id": uuid4()}
        )

        with patch.object(runner, "_get_video_asset_id", return_value=uuid4()):
            with patch.object(
                runner,
                "_perform_visual_validation",
                return_value={"valid": True, "reason": "Valid"},
            ):
                mock_pub = MagicMock()
                mock_pub.id = uuid4()
                mock_pub.status = PublicationStatus.PUBLISHED
                mock_pub.provider_metadata = {"privacyStatus": "public"}
                mock_deps["publication_repository"].list_by_execution = AsyncMock(
                    return_value=[mock_pub]
                )

                result = await runner.run_production_e2e({})
                assert result["validation_result"] == "FAILED"
                assert "privacyStatus is 'public'" in result["error"]
