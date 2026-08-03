"""Unit tests for the synchronous workflow runtime with history and metrics tracking."""

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
    WorkflowExecutionErrorRepository,
    WorkflowExecutionHistoryRepository,
    WorkflowExecutionMetricRepository,
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


@pytest.fixture
def error_repository():
    return AsyncMock(spec=WorkflowExecutionErrorRepository)


@pytest.fixture
def metric_repository():
    return AsyncMock(spec=WorkflowExecutionMetricRepository)


@pytest.mark.asyncio
async def test_workflow_runtime_run_success_with_metrics(
    job_repository: AsyncMock,
    execution_repository: AsyncMock,
    step_repository: AsyncMock,
    history_repository: AsyncMock,
    error_repository: AsyncMock,
    metric_repository: AsyncMock,
):
    runtime = WorkflowRuntime(
        job_repository,
        execution_repository,
        step_repository,
        history_repository,
        error_repository,
        metric_repository,
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
    assert metric_repository.create.called
    # duration_ms, step_count, success_count, failure_count
    assert metric_repository.create.call_count == 4

    metric_calls = [call.args[0].metric_type for call in metric_repository.create.call_args_list]
    assert "duration_ms" in metric_calls
    assert "step_count" in metric_calls
    assert "success_count" in metric_calls
    assert "failure_count" in metric_calls


@pytest.mark.asyncio
async def test_workflow_runtime_failure_records_metrics(
    job_repository: AsyncMock,
    execution_repository: AsyncMock,
    step_repository: AsyncMock,
    history_repository: AsyncMock,
    error_repository: AsyncMock,
    metric_repository: AsyncMock,
):
    runtime = WorkflowRuntime(
        job_repository,
        execution_repository,
        step_repository,
        history_repository,
        error_repository,
        metric_repository,
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
    assert metric_repository.create.called
    assert metric_repository.create.call_count == 4
    
    # Check failure_count is recorded correctly
    failure_metric = next(
        call.args[0] for call in metric_repository.create.call_args_list 
        if call.args[0].metric_type == "failure_count"
    )
    assert failure_metric.metric_value == 1.0
