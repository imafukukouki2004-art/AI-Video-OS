import asyncio
import json
import logging
import os
import sys
from uuid import UUID

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.api.config import get_settings
from apps.api.database import Database
from apps.api.publishing import (
    AutomaticPublishingCoordinator,
    CredentialCipher,
    PublicationRepository,
    PublishingConnectionRepository,
    PublishingCredentialRepository,
    PublishingProviderResolver,
    PublishingQueueService,
    PublishingService,
    YouTubeCredentialResolver,
    YouTubeCredentialSettings,
    YouTubePublishingProvider,
)
from apps.api.repositories import (
    AssetRepository,
    JobRepository,
    ProjectRepository,
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
from apps.api.storage import S3ObjectStorage
from apps.api.video_rendering.ffmpeg import FFmpegVideoRenderer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("production_e2e")


PROJECT_ID_ENV = "AI_VIDEO_OS_PRODUCTION_E2E_PROJECT_ID"


def get_required_project_id() -> UUID:
    """Parse the explicitly selected, pre-existing Production Project ID."""
    raw_project_id = os.getenv(PROJECT_ID_ENV)
    if not raw_project_id:
        raise ValueError(f"{PROJECT_ID_ENV} must identify an existing Project")
    try:
        return UUID(raw_project_id)
    except ValueError as error:
        raise ValueError(f"{PROJECT_ID_ENV} must be a valid UUID") from error


async def run_validation() -> int:
    """Main entry point for production E2E validation."""
    if os.getenv("AI_VIDEO_OS_RUN_PRODUCTION_E2E") != "true":
        print("🛑 ERROR: Explicit opt-in required.")
        print("Please set AI_VIDEO_OS_RUN_PRODUCTION_E2E=true to run this script.")
        return 1

    try:
        project_id = get_required_project_id()
    except ValueError as error:
        print(f"🛑 ERROR: {error}")
        return 1

    settings = get_settings()
    database = Database(settings)
    storage = S3ObjectStorage(settings)

    try:
        async with database.session_factory() as session:
            project_repo = ProjectRepository(session)
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
            connection_repo = PublishingConnectionRepository(session)
            credential_repo = PublishingCredentialRepository(session)

            credential_resolver = YouTubeCredentialResolver(
                connection_repo,
                credential_repo,
                CredentialCipher(settings.youtube_credential_encryption_key),
                settings.youtube_client_id,
                settings.youtube_client_secret,
            )
            youtube_provider = YouTubePublishingProvider(
                storage,
                YouTubeCredentialSettings(
                    client_id=settings.youtube_client_id,
                    client_secret=settings.youtube_client_secret,
                    refresh_token=settings.youtube_refresh_token,
                ),
                credential_source=credential_resolver,
                privacy_status="private",
            )
            provider_resolver = PublishingProviderResolver({"youtube": youtube_provider})
            publishing_service = PublishingService(
                publication_repo,
                asset_repo,
                provider_resolver,
            )
            publishing_queue = PublishingQueueService(publication_repo)
            auto_publishing = AutomaticPublishingCoordinator(
                execution_repo,
                artifact_repo,
                publication_repo,
                publishing_service,
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
                PromptBuilder(),
                FFmpegVideoRenderer(),
                auto_publishing,
            )

            runner = ValidationRunner(
                runtime_service,
                project_repo,
                workflow_repo,
                step_repo,
                artifact_repo,
                asset_repo,
                publication_repo,
                storage,
            )

            # Execute Validation
            config = {
                "project_id": project_id,
                "text_prompt": "Write a one-sentence summary of the future of AI.",
                "image_prompt": (
                    "A serene landscape with a futuristic laboratory, digital art style."
                ),
            }

            print("🚀 Starting Production E2E Validation...")
            report = await runner.run_production_e2e(config)

            # Output Safe Report
            print("\n--- VALIDATION REPORT ---")
            print(json.dumps(report, indent=2))
            print("-------------------------\n")

            if report.get("validation_result") == "SUCCESS":
                print("✅ Production E2E Validation PASSED!")
                return 0
            print("❌ Production E2E Validation FAILED.")
            return 1
    finally:
        await storage.close()
        await database.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(run_validation()))
