"""Unit tests for the synchronous workflow runtime with step definitions."""

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


@pytest.mark.asyncio
async def test_workflow_runtime_run_success(
    job_repository: AsyncMock,
    execution_repository: AsyncMock,
    step_repository: AsyncMock,
):
    runtime = WorkflowRuntime(job_repository, execution_repository, step_repository)
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
    assert step_repository.update.called
    assert job_repository.create.called


@pytest.mark.asyncio
async def test_workflow_runtime_no_steps(
    job_repository: AsyncMock,
    execution_repository: AsyncMock,
    step_repository: AsyncMock,
):
    runtime = WorkflowRuntime(job_repository, execution_repository, step_repository)
    workflow = Workflow(id=uuid4(), config={})

    mock_execution = WorkflowExecution(
        id=uuid4(), workflow_id=workflow.id, status=WorkflowExecutionStatus.PENDING
    )
    execution_repository.create.return_value = mock_execution
    execution_repository.update.side_effect = lambda id, data: WorkflowExecution(id=id, **data)

    step_repository.list_by_workflow.return_value = []

    result = await runtime.run(workflow)

    assert result["status"] == "completed"
    assert len(result["jobs"]) == 0
    assert execution_repository.update.called
