"""Unit tests for the synchronous workflow runtime with history tracking."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from apps.api.domain.models import (
    Workflow,
    WorkflowExecution,
    WorkflowExecutionStatus,
    WorkflowStep,
    WorkflowStepStatus,
)
from apps.api.repositories import (
    JobRepository,
    WorkflowExecutionHistoryRepository,
    WorkflowExecutionRepository,
    WorkflowStepRepository,
)
from apps.api.workflow.runtime import WorkflowRuntime


@pytest.fixture
def job_repository():
    return AsyncMock(spec=JobRepository)


@pytest.fixture
def execution_repository():
    return AsyncMock(spec=WorkflowExecutionRepository)


@pytest.fixture
def step_repository():
    return AsyncMock(spec=WorkflowStepRepository)


@pytest.fixture
def history_repository():
    return AsyncMock(spec=WorkflowExecutionHistoryRepository)


@pytest.mark.asyncio
async def test_workflow_runtime_run_success_with_history(
    job_repository: AsyncMock,
    execution_repository: AsyncMock,
    step_repository: AsyncMock,
    history_repository: AsyncMock,
):
    runtime = WorkflowRuntime(
        job_repository, execution_repository, step_repository, history_repository
    )
    workflow = Workflow(id=uuid4(), config={})

    # Mock execution creation and updates
    mock_execution = WorkflowExecution(
        id=uuid4(), workflow_id=workflow.id, status=WorkflowExecutionStatus.PENDING
    )
    execution_repository.create.return_value = mock_execution
    execution_repository.update.side_effect = lambda id, data: WorkflowExecution(id=id, **data)

    # Mock step retrieval and updates
    mock_step = WorkflowStep(
        id=uuid4(),
        workflow_id=workflow.id,
        name="step1",
        step_type="test",
        order=0,
        config={"key": "val"},
        status=WorkflowStepStatus.PENDING,
    )
    step_repository.list_by_workflow.return_value = [mock_step]
    step_repository.update.side_effect = lambda id, data: WorkflowStep(id=id, **data)

    # Mock job creation and updates
    job_repository.create.return_value = AsyncMock(id=uuid4())
    job_repository.update.return_value = AsyncMock(id=uuid4())

    result = await runtime.run(workflow)

    assert result["status"] == "completed"
    assert "execution_id" in result
    assert len(result["jobs"]) == 1
    assert execution_repository.create.called
    assert step_repository.list_by_workflow.called
    assert history_repository.create.called
    # Check that at least 3 history records were created (Start, Step Start, Step End, Complete)
    assert history_repository.create.call_count >= 3


@pytest.mark.asyncio
async def test_workflow_runtime_failure_with_history(
    job_repository: AsyncMock,
    execution_repository: AsyncMock,
    step_repository: AsyncMock,
    history_repository: AsyncMock,
):
    runtime = WorkflowRuntime(
        job_repository, execution_repository, step_repository, history_repository
    )
    workflow = Workflow(id=uuid4(), config={})

    mock_execution = WorkflowExecution(
        id=uuid4(), workflow_id=workflow.id, status=WorkflowExecutionStatus.PENDING
    )
    execution_repository.create.return_value = mock_execution
    execution_repository.update.side_effect = lambda id, data: WorkflowExecution(id=id, **data)

    mock_step = WorkflowStep(
        id=uuid4(), workflow_id=workflow.id, name="fail_step", step_type="test", order=0, config={}
    )
    step_repository.list_by_workflow.return_value = [mock_step]

    # Force failure during job update
    job_repository.create.return_value = AsyncMock(id=uuid4())
    job_repository.update.side_effect = Exception("Simulated failure")

    result = await runtime.run(workflow)

    assert result["status"] == "failed"
    assert history_repository.create.called
    # Check that failure history was recorded
    last_call = history_repository.create.call_args_list[-1]
    assert last_call.args[0].to_status == "failed"


@pytest.mark.asyncio
async def test_workflow_runtime_guard_prevents_execution(
    job_repository: AsyncMock,
    execution_repository: AsyncMock,
    step_repository: AsyncMock,
    history_repository: AsyncMock,
):
    runtime = WorkflowRuntime(
        job_repository, execution_repository, step_repository, history_repository
    )
    workflow = Workflow(id=uuid4(), config={})

    # Mock no steps (invalid)
    step_repository.list_by_workflow.return_value = []

    result = await runtime.run(workflow)

    assert result["status"] == "failed"
    assert "validation_errors" in result
    assert execution_repository.create.called is False
