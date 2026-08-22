import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

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
def mock_repositories():
    return {
        "workflow": MagicMock(spec=WorkflowRepository),
        "step": MagicMock(spec=WorkflowStepRepository),
        "publication": MagicMock(spec=PublicationRepository),
    }


@pytest.mark.asyncio
async def test_production_e2e_foundation_flow_success(mock_repositories):
    """
    Test the entire validation runner flow with mocks.
    Ensures that steps are correctly orchestrated and the report is generated.
    """
    mock_runtime_service = MagicMock(spec=WorkflowRuntimeService)
    mock_storage = MagicMock(spec=ObjectStorage)

    with patch.dict(os.environ, {"AI_VIDEO_OS_RUN_PRODUCTION_E2E": "true"}):
        runner = ValidationRunner(
            workflow_runtime_service=mock_runtime_service,
            workflow_repository=mock_repositories["workflow"],
            step_repository=mock_repositories["step"],
            artifact_repository=MagicMock(spec=WorkflowArtifactRepository),
            asset_repository=MagicMock(spec=AssetRepository),
            publication_repository=mock_repositories["publication"],
            storage=mock_storage,
        )

        # 1. Mock Workflow Setup
        workflow_id = uuid4()
        execution_id = uuid4()
        mock_workflow = MagicMock(id=workflow_id)
        mock_repositories["workflow"].create = AsyncMock(return_value=mock_workflow)
        mock_repositories["step"].create = AsyncMock()

        # 2. Mock Execution Success
        mock_runtime_service.execute_workflow = AsyncMock(
            return_value={"status": "completed", "execution_id": execution_id}
        )

        # 3. Mock Visual Validation (skip for now as it needs file ops)
        with patch.object(runner, "_get_video_asset_id", return_value=uuid4()):
            with patch.object(
                runner,
                "_perform_visual_validation",
                return_value={"valid": True, "reason": "Frame appears valid"},
            ):
                # 4. Mock Publication Success
                mock_publication = MagicMock()
                mock_publication.id = uuid4()
                mock_publication.status = "published"
                mock_publication.external_id = "yt_123"
                mock_publication.external_url = "https://youtube.com/watch?v=yt_123"
                mock_publication.provider_metadata = {"privacyStatus": "private"}
                mock_repositories["publication"].list_by_execution = AsyncMock(
                    return_value=[mock_publication]
                )

                # Execute
                report = await runner.run_production_e2e({})

                # Assertions
                assert report["validation_result"] == "SUCCESS"
                assert report["workflow_status"] == "completed"
                assert report["publication_status"] == "published"
                assert report["youtube_external_id"] == "yt_123"
                assert report["privacy_status"] == "private"
                assert "error" not in report
