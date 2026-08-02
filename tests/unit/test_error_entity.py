"""Unit tests for the WorkflowExecutionError entity."""

from uuid import uuid4

from apps.api.domain.models import WorkflowExecutionError


def test_create_error_entity():
    execution_id = uuid4()
    step_id = uuid4()
    error = WorkflowExecutionError(
        id=uuid4(),
        workflow_execution_id=execution_id,
        workflow_step_id=step_id,
        error_code="TEST_ERROR",
        error_message="Test message",
        error_type="ValueError",
    )
    assert error.error_code == "TEST_ERROR"
    assert error.workflow_execution_id == execution_id
    assert error.workflow_step_id == step_id
