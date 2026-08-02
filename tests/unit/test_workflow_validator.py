"""Unit tests for the workflow validator."""

from uuid import uuid4

import pytest

from apps.api.domain.models import Workflow, WorkflowStep, WorkflowStepStatus
from apps.api.workflow.validator import WorkflowValidator


@pytest.mark.asyncio
async def test_validator_success():
    validator = WorkflowValidator()
    workflow = Workflow(id=uuid4())
    steps = [
        WorkflowStep(
            id=uuid4(),
            name="step1",
            step_type="test",
            order=0,
            config={},
            status=WorkflowStepStatus.PENDING,
        ),
        WorkflowStep(
            id=uuid4(),
            name="step2",
            step_type="test",
            order=1,
            config={},
            status=WorkflowStepStatus.PENDING,
        ),
    ]

    result = await validator.validate(workflow, steps)
    assert result.valid is True
    assert len(result.errors) == 0


@pytest.mark.asyncio
async def test_validator_no_steps():
    validator = WorkflowValidator()
    workflow = Workflow(id=uuid4())
    steps = []

    result = await validator.validate(workflow, steps)
    assert result.valid is False
    assert "Workflow has no steps defined." in result.errors


@pytest.mark.asyncio
async def test_validator_wrong_order():
    validator = WorkflowValidator()
    workflow = Workflow(id=uuid4())
    steps = [
        WorkflowStep(
            id=uuid4(),
            name="step1",
            step_type="test",
            order=1,
            config={},
            status=WorkflowStepStatus.PENDING,
        ),
        WorkflowStep(
            id=uuid4(),
            name="step2",
            step_type="test",
            order=0,
            config={},
            status=WorkflowStepStatus.PENDING,
        ),
    ]

    result = await validator.validate(workflow, steps)
    assert result.valid is False
    assert "Workflow steps are not in correct sequential order." in result.errors


@pytest.mark.asyncio
async def test_validator_missing_fields():
    validator = WorkflowValidator()
    workflow = Workflow(id=uuid4())
    steps = [
        WorkflowStep(
            id=uuid4(),
            name="",
            step_type="",
            order=0,
            config=None,
            status=WorkflowStepStatus.PENDING,
        )
    ]

    result = await validator.validate(workflow, steps)
    assert result.valid is False
    assert any("missing a name" in e for e in result.errors)
    assert any("missing a step type" in e for e in result.errors)
    assert any("null configuration" in e for e in result.errors)
