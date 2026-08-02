"""Unit tests for the workflow runtime."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from apps.api.domain.models import (
    Job,
    JobStatus,
    Workflow,
    WorkflowExecution,
    WorkflowExecutionStatus,
)
from apps.api.repositories.sqlalchemy import JobRepository, WorkflowExecutionRepository
from apps.api.workflow.runtime import WorkflowRuntime


@pytest.fixture
def job_repository() -> JobRepository:
    return AsyncMock(spec=JobRepository)


@pytest.fixture
def execution_repository() -> WorkflowExecutionRepository:
    return AsyncMock(spec=WorkflowExecutionRepository)


@pytest.mark.asyncio
async def test_workflow_runtime_run_success(
    job_repository: AsyncMock, execution_repository: AsyncMock
):
    runtime = WorkflowRuntime(job_repository, execution_repository)
    workflow = Workflow(id=uuid4(), config={"steps": [{"name": "step1", "input": {"key": "val"}}]})

    # Mock execution creation and updates
    mock_execution = WorkflowExecution(
        id=uuid4(), workflow_id=workflow.id, status=WorkflowExecutionStatus.PENDING
    )
    execution_repository.create.return_value = mock_execution
    execution_repository.update.side_effect = lambda id, data: WorkflowExecution(id=id, **data)

    # Mock job creation and updates
    mock_job = Job(id=uuid4(), name="step1", status=JobStatus.PENDING)
    job_repository.create.return_value = mock_job
    job_repository.update.side_effect = lambda id, data: Job(id=id, **data)

    result = await runtime.run(workflow)

    assert result["status"] == "completed"
    assert result["execution_id"] == mock_execution.id
    assert len(result["jobs"]) == 1
    assert execution_repository.create.called
    assert execution_repository.update.called
    assert job_repository.create.called
    assert job_repository.update.called


@pytest.mark.asyncio
async def test_workflow_runtime_no_steps(
    job_repository: AsyncMock, execution_repository: AsyncMock
):
    runtime = WorkflowRuntime(job_repository, execution_repository)
    workflow = Workflow(id=uuid4(), config={})

    mock_execution = WorkflowExecution(
        id=uuid4(), workflow_id=workflow.id, status=WorkflowExecutionStatus.PENDING
    )
    execution_repository.create.return_value = mock_execution
    execution_repository.update.side_effect = lambda id, data: WorkflowExecution(id=id, **data)

    result = await runtime.run(workflow)

    assert result["status"] == "completed"
    assert result["jobs"] == []
    assert not job_repository.create.called
