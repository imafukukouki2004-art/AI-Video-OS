"""Unit tests for the workflow runtime."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from apps.api.domain.models import Job, JobStatus, Workflow
from apps.api.repositories.sqlalchemy import JobRepository
from apps.api.workflow.runtime import WorkflowRuntime


@pytest.fixture
def job_repository() -> JobRepository:
    return AsyncMock(spec=JobRepository)


@pytest.mark.asyncio
async def test_workflow_runtime_run_success(job_repository: AsyncMock):
    runtime = WorkflowRuntime(job_repository)
    workflow = Workflow(id=uuid4(), config={"steps": [{"name": "step1", "input": {"key": "val"}}]})

    # Mock job creation and updates
    mock_job = Job(id=uuid4(), name="step1", status=JobStatus.PENDING)
    job_repository.create.return_value = mock_job
    job_repository.update.side_effect = lambda id, data: Job(id=id, **data)

    result = await runtime.run(workflow)

    assert result["status"] == "completed"
    assert len(result["jobs"]) == 1
    assert job_repository.create.called
    assert job_repository.update.called


@pytest.mark.asyncio
async def test_workflow_runtime_no_steps(job_repository: AsyncMock):
    runtime = WorkflowRuntime(job_repository)
    workflow = Workflow(id=uuid4(), config={})

    result = await runtime.run(workflow)

    assert result["status"] == "completed"
    assert result["jobs"] == []
    assert not job_repository.create.called
