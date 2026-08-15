import logging
import os
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from apps.api.domain.models import Workflow
from apps.api.domain.schemas import WorkflowCreate, WorkflowStepCreate
from apps.api.publishing.models import PublicationStatus
from apps.api.publishing.repository import PublicationRepository
from apps.api.repositories.sqlalchemy import (
    AssetRepository,
    WorkflowArtifactRepository,
    WorkflowRepository,
    WorkflowStepRepository,
)
from apps.api.services.workflow_runtime import WorkflowRuntimeService
from apps.api.storage import ObjectStorage
from apps.api.workflow.validation_utils import VisualValidator

logger = logging.getLogger(__name__)


class ValidationRunner:
    """Orchestrates Production End-to-End Validation."""

    def __init__(
        self,
        workflow_runtime_service: WorkflowRuntimeService,
        workflow_repository: WorkflowRepository,
        step_repository: WorkflowStepRepository,
        artifact_repository: WorkflowArtifactRepository,
        asset_repository: AssetRepository,
        publication_repository: PublicationRepository,
        storage: ObjectStorage,
    ) -> None:
        self.workflow_runtime_service = workflow_runtime_service
        self.workflow_repository = workflow_repository
        self.step_repository = step_repository
        self.artifact_repository = artifact_repository
        self.asset_repository = asset_repository
        self.publication_repository = publication_repository
        self.storage = storage
        self.visual_validator = VisualValidator()

    async def run_production_e2e(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Executes a full production E2E validation flow.
        Requires explicit opt-in via environment variable.
        """
        if os.getenv("AI_VIDEO_OS_RUN_PRODUCTION_E2E") != "true":
            return {
                "status": "skipped",
                "reason": "Explicit opt-in required (AI_VIDEO_OS_RUN_PRODUCTION_E2E=true)",
            }

        report: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "validation_result": "FAILED",
            "details": {},
        }

        try:
            # 1. Setup Validation Workflow
            workflow = await self._setup_validation_workflow(config)
            report["workflow_id"] = str(workflow.id)

            # 2. Execute Workflow
            logger.info(f"Starting Production E2E Validation for Workflow: {workflow.id}")
            result = await self.workflow_runtime_service.execute_workflow(workflow.id)
            execution_id = result.get("execution_id")
            report["execution_id"] = str(execution_id)
            report["workflow_status"] = result.get("status")

            if result.get("status") != "completed":
                report["error"] = result.get("error")
                return report

            if not isinstance(execution_id, UUID):
                report["error"] = "Invalid execution ID returned from runtime"
                return report

            # 3. Visual Validation
            # Find the video asset generated
            video_asset_id = await self._get_video_asset_id(execution_id)
            if video_asset_id:
                report["video_asset_id"] = str(video_asset_id)
                visual_check = await self._perform_visual_validation(video_asset_id)
                report["visual_validation"] = visual_check
                if not visual_check["valid"]:
                    return report
            else:
                report["error"] = "Video asset not found after completion"
                return report

            # 4. Publishing Validation (Async Wait & Strict Privacy)
            import asyncio

            timeout_seconds = 60
            poll_interval = 2
            elapsed = 0
            publication = None

            while elapsed < timeout_seconds:
                publications = await self.publication_repository.list_by_execution(execution_id)
                if publications:
                    publication = publications[0]
                    if publication.status in (
                        PublicationStatus.PUBLISHED,
                        PublicationStatus.FAILED,
                    ):
                        break
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            if not publication:
                report["error"] = "Publication record not found"
                return report

            report["publication_id"] = str(publication.id)
            report["publication_status"] = publication.status
            report["youtube_external_id"] = publication.external_id
            report["youtube_url"] = publication.external_url
            privacy_status = publication.provider_metadata.get(
                "privacyStatus"
            ) or publication.provider_metadata.get("privacy_status")
            report["privacy_status"] = privacy_status

            if publication.status == PublicationStatus.PUBLISHED:
                if privacy_status == "private":
                    report["validation_result"] = "SUCCESS"
                else:
                    report["error"] = (
                        "Validation failed: "
                        f"privacyStatus is '{privacy_status}', expected 'private'"
                    )
            elif publication.status == PublicationStatus.FAILED:
                report["error"] = f"Publication failed with error: {publication.error_message}"
            else:
                report["error"] = f"Publication timed out in status: {publication.status}"

            return report

        except Exception as e:
            logger.exception("Production E2E Validation failed with unexpected error")
            report["error"] = str(e)
            return report

    async def _setup_validation_workflow(self, config: dict[str, Any]) -> Workflow:
        """Create a workflow configured for production E2E validation."""
        workflow_in = WorkflowCreate(
            name=f"Production E2E Validation {datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
            workflow_type="production_validation",
            project_id=uuid4(),  # Placeholder project ID
            config={
                "auto_publish": True,
                "publishing_config": {
                    "provider": "youtube",
                    "privacyStatus": "private",  # Force private
                },
            },
        )
        workflow = await self.workflow_repository.create(workflow_in)

        # Step 1: Text Generation
        text_step_in = WorkflowStepCreate(
            workflow_id=workflow.id,
            name="Production Text Gen",
            step_type="ai",
            order=1,
            config={
                "provider": "openai",
                "operation": "text_generation",
                "prompt": config.get("text_prompt", "Write a short poem about AI."),
            },
        )
        await self.step_repository.create(text_step_in)

        # Step 2: Image Generation
        image_step_in = WorkflowStepCreate(
            workflow_id=workflow.id,
            name="Production Image Gen",
            step_type="ai",
            order=2,
            config={
                "provider": "openai",
                "operation": "image_generation",
                "prompt": config.get(
                    "image_prompt", "A futuristic city in the style of Cyberpunk."
                ),
            },
        )
        image_step = await self.step_repository.create(image_step_in)

        # Step 3: Video Render
        video_step_in = WorkflowStepCreate(
            workflow_id=workflow.id,
            name="Production Video Render",
            step_type="video_render",
            order=3,
            config={
                "image_source": f"{{{{{image_step.id}.image}}}}",
                "duration": 5,
            },
        )
        await self.step_repository.create(video_step_in)

        return workflow

    async def _get_video_asset_id(self, execution_id: UUID) -> UUID | None:
        """Find the video asset ID for a given execution."""
        artifacts = await self.artifact_repository.list_by_execution(execution_id)
        for artifact in artifacts:
            if artifact.artifact_type == "video":
                return artifact.asset_id
        return None

    async def _perform_visual_validation(self, asset_id: UUID) -> dict[str, Any]:
        """Download asset and check for black frames."""
        import tempfile

        import httpx

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_video = os.path.join(tmp_dir, f"{asset_id}.mp4")
            temp_image = os.path.join(tmp_dir, f"{asset_id}.png")
            try:
                # 1. Get asset details
                asset = await self.asset_repository.get_by_id(asset_id)
                if not asset:
                    return {"valid": False, "reason": "Asset not found"}
                object_key = asset.object_key

                # 2. Get download URL
                url = await self.storage.create_presigned_download_url(object_key, expires_in=3600)

                # 2. Download
                async with httpx.AsyncClient() as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    with open(temp_video, "wb") as f:  # noqa: ASYNC230
                        f.write(response.content)

                # 3. Validate
                extracted = self.visual_validator.extract_frame(temp_video, temp_image)
                if not extracted:
                    return {"valid": False, "reason": "Failed to extract frame"}

                valid, reason = self.visual_validator.is_not_black_or_blank(temp_image)
                return {"valid": valid, "reason": reason}
            except Exception as e:
                logger.error(f"Visual validation failed: {e!s}")
                return {"valid": False, "reason": str(e)}
