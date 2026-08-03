import pytest

from apps.api.workflow.context import VariableResolver, WorkflowContext


def test_workflow_context_set_get():
    context = WorkflowContext()
    context.set_step_output("step1", "output1")

    assert context.get_step_output("step1") == "output1"
    assert context.get_step_output("nonexistent") is None


def test_variable_resolver_success():
    context = WorkflowContext()
    context.set_step_output("step1", "Hello")
    context.set_step_output("step2", "World")

    resolver = VariableResolver(context)

    text = "Say {{step1.output}} to the {{step2.output}}"
    resolved = resolver.resolve(text)

    assert resolved == "Say Hello to the World"


def test_variable_resolver_with_uuid():
    context = WorkflowContext()
    step_id = "550e8400-e29b-41d4-a716-446655440000"
    context.set_step_output(step_id, "UUID Output")

    resolver = VariableResolver(context)

    text = "Result: {{550e8400-e29b-41d4-a716-446655440000.output}}"
    resolved = resolver.resolve(text)

    assert resolved == "Result: UUID Output"


def test_variable_resolver_unresolved_error():
    context = WorkflowContext()
    resolver = VariableResolver(context)

    text = "Missing: {{missing.output}}"

    with pytest.raises(ValueError, match="Unresolved variable: {{missing.output}}"):
        resolver.resolve(text)


def test_variable_resolver_empty_text():
    context = WorkflowContext()
    resolver = VariableResolver(context)

    assert resolver.resolve("") == ""
    assert resolver.resolve(None) is None
