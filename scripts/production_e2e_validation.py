import asyncio
import json
import logging
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.api.config import settings
from apps.api.database import async_session
from apps.api.publishing.automatic import AutomaticPublishingCoordinator
from apps.api.publishing.queue import PublishingQueueService
from apps.api.publishing.repository import PublicationRepository
from apps.api.repositories import (
    AssetRepository,
    JobRepository,
    WorkflowArtifactRepository,
    WorkflowExecutionErrorRepository,
    WorkflowExecutionHistoryRepository,
    WorkflowExecutionMetricRepository,
    WorkflowExecutionRepository,
    WorkflowRepository,
    WorkflowStepRepository,
)
from apps.api.services.prompt_builder import PromptBuilder
from apps.api.services.validation_runner import ValidationRunner
from apps.api.services.workflow_runtime import WorkflowRuntimeService
from apps.api.storage import MinioObjectStorage
from apps.api.video_rendering.ffmpeg import FFmpegVideoRenderer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("production_e2e")


async def run_validation():
    """Main entry point for production E2E validation."""
    if os.getenv("AI_VIDEO_OS_RUN_PRODUCTION_E2E") != "true":
        print("🛑 ERROR: Explicit opt-in required.")
        print("Please set AI_VIDEO_OS_RUN_PRODUCTION_E2E=true to run this script.")
        sys.exit(1)

    async with async_session() as session:
        # Initialize Repositories
        workflow_repo = WorkflowRepository(session)
        step_repo = WorkflowStepRepository(session)
        job_repo = JobRepository(session)
        execution_repo = WorkflowExecutionRepository(session)
        history_repo = WorkflowExecutionHistoryRepository(session)
        error_repo = WorkflowExecutionErrorRepository(session)
        metric_repo = WorkflowExecutionMetricRepository(session)
        artifact_repo = WorkflowArtifactRepository(session)
        asset_repo = AssetRepository(session)
        publication_repo = PublicationRepository(session)

        # Initialize Services
        storage = MinioObjectStorage(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            bucket=settings.MINIO_BUCKET,
            secure=settings.MINIO_SECURE,
        )

        prompt_builder = PromptBuilder(session)  # Assuming PromptBuilder needs session
        video_renderer = FFmpegVideoRenderer(storage)

        # publishing_service = PublishingService(
        #     publication_repo,
        #     asset_repo,
        #     storage,
        #     # Add other dependencies as needed
        # )

        publishing_queue = PublishingQueueService()  # Mock or real depending on environment

        auto_publishing = AutomaticPublishingCoordinator(
            publication_repo,
            artifact_repo,
            asset_repo,
            publishing_queue,
        )

        runtime_service = WorkflowRuntimeService(
            workflow_repo,
            job_repo,
            execution_repo,
            step_repo,
            history_repo,
            error_repo,
            metric_repo,
            artifact_repo,
            asset_repo,
            storage,
            prompt_builder,
            video_renderer,
            auto_publishing,
        )

        runner = ValidationRunner(
            runtime_service,
            workflow_repo,
            step_repo,
            artifact_repo,
            asset_repo,
            publication_repo,
            storage,
        )

        # Execute Validation
        config = {
            "text_prompt": "Write a one-sentence summary of the future of AI.",
            "image_prompt": "A serene landscape with a futuristic laboratory, digital art style.",
        }

        print("🚀 Starting Production E2E Validation...")
        report = await runner.run_production_e2e(config)

        # Output Safe Report
        print("\n--- VALIDATION REPORT ---")
        print(json.dumps(report, indent=2))
        print("-------------------------\n")

        if report.get("validation_result") == "SUCCESS":
            print("✅ Production E2E Validation PASSED!")
            sys.exit(0)
        else:
            print("❌ Production E2E Validation FAILED.")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_validation())
