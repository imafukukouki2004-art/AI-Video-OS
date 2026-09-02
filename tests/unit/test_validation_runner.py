import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from apps.api.domain.models import Workflow, WorkflowStep
from apps.api.publishing.automatic import AutomaticPublishingConfig
from apps.api.publishing.models import PublicationStatus
from apps.api.publishing.repository import PublicationRepository
from apps.api.repositories.sqlalchemy import (
    AssetRepository,
    ProjectRepository,
    WorkflowArtifactRepository,
    WorkflowRepository,
    WorkflowStepRepository,
)
from apps.api.services.validation_runner import ValidationRunner
from apps.api.services.workflow_runtime import WorkflowRuntimeService
from apps.api.storage import ObjectStorage
from apps.api.workflow.validator import WorkflowValidator

PROJECT_ID = uuid4()


@pytest.fixture
def mock_deps():
    dependencies = {
        "workflow_runtime_service": MagicMock(spec=WorkflowRuntimeService),
        "project_repository": MagicMock(spec=ProjectRepository),
        "workflow_repository": MagicMock(spec=WorkflowRepository),
        "step_repository": MagicMock(spec=WorkflowStepRepository),
        "artifact_repository": MagicMock(spec=WorkflowArtifactRepository),
        "asset_repository": MagicMock(spec=AssetRepository),
        "publication_repository": MagicMock(spec=PublicationRepository),
        "storage": MagicMock(spec=ObjectStorage),
    }
    dependencies["project_repository"].get_by_id = AsyncMock(return_value=MagicMock(id=PROJECT_ID))
    return dependencies


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

        await runner._setup_validation_workflow({"project_id": PROJECT_ID})

        args, _ = mock_deps["workflow_repository"].create.call_args
        workflow_in = args[0]
        assert workflow_in.project_id == PROJECT_ID
        assert workflow_in.config["auto_publish"] is True
        assert workflow_in.config["provider"] == "youtube"
        assert "publishing_config" not in workflow_in.config
        publishing_config = AutomaticPublishingConfig.model_validate(workflow_in.config)
        assert publishing_config.auto_publish is True
        assert publishing_config.provider == "youtube"


@pytest.mark.asyncio
async def test_validation_runner_builds_runtime_compatible_video_dependency(mock_deps):
    workflow_id = uuid4()
    workflow = Workflow(
        id=workflow_id,
        project_id=PROJECT_ID,
        workflow_type="production_validation",
        config={},
    )
    created_steps: list[WorkflowStep] = []

    async def create_step(step_in):
        step = WorkflowStep(id=uuid4(), **step_in.model_dump())
        created_steps.append(step)
        return step

    mock_deps["workflow_repository"].create = AsyncMock(return_value=workflow)
    mock_deps["step_repository"].create = AsyncMock(side_effect=create_step)

    runner = ValidationRunner(**mock_deps)
    await runner._setup_validation_workflow({"project_id": PROJECT_ID})

    image_step = created_steps[1]
    video_step = created_steps[2]
    assert video_step.config["operation"] == "video_render"
    assert video_step.config["input_asset"] == f"{{{{{image_step.id}.asset}}}}"
    assert "image_source" not in video_step.config

    validation = await WorkflowValidator().validate(workflow, created_steps)
    assert validation.valid is True
    assert validation.errors == []


@pytest.mark.asyncio
async def test_validation_runner_requires_existing_project_before_writes(mock_deps):
    runner = ValidationRunner(**mock_deps)
    mock_deps["project_repository"].get_by_id = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="does not exist"):
        await runner._setup_validation_workflow({"project_id": PROJECT_ID})

    mock_deps["workflow_repository"].create.assert_not_called()
    mock_deps["step_repository"].create.assert_not_called()


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

                result = await runner.run_production_e2e({"project_id": PROJECT_ID})
                assert result["validation_result"] == "FAILED"
                assert "privacyStatus is 'public'" in result["error"]
