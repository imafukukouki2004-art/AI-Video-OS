from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from apps.api.ai_providers.mock import MockAIProvider
from apps.api.domain.models import WorkflowStep, WorkflowStepStatus
from apps.api.workflow.runtime import WorkflowRuntime


@pytest.mark.asyncio
async def test_prompt_composition_runs_through_workflow_runtime() -> None:
    repositories = [AsyncMock() for _ in range(8)]
    job_repo, execution_repo, step_repo, history_repo, error_repo, metric_repo, _, _ = repositories
    runtime = WorkflowRuntime(*repositories, MagicMock())
    workflow = MagicMock(id=uuid4())
    step = WorkflowStep(
        id=uuid4(),
        name="ComposePrompt",
        step_type="ai",
        order=1,
        config={
            "provider": "mock",
            "operation": "text_generation",
            "prompt": "Create a concise outline",
            "system_prompt": "You are a video producer",
        },
        status=WorkflowStepStatus.PENDING,
    )
    step_repo.list_by_workflow.return_value = [step]
    execution_repo.create.return_value = MagicMock(id=uuid4(), status="pending")
    execution_repo.update.return_value = MagicMock(id=uuid4(), status="running")
    job_repo.create.return_value = MagicMock(id=uuid4())
    job_repo.update.return_value = MagicMock(id=uuid4())

    with (
        patch.object(runtime.validator, "validate", return_value=MagicMock(valid=True)),
        patch(
            "apps.api.workflow.runtime.AIProviderFactory.create",
            return_value=MockAIProvider(),
        ),
    ):
        result = await runtime.run(workflow)

    assert result["status"] == "completed"
    completed_job = job_repo.update.call_args_list[-1].args[1]
    assert completed_job["output_data"]["result"] == ("Mock response for: Create a concise outline")
    assert completed_job["output_data"]["metadata"]["system_prompt"] == ("You are a video producer")
    error_repo.create.assert_not_called()
    history_repo.create.assert_awaited()
    metric_repo.create.assert_awaited()
