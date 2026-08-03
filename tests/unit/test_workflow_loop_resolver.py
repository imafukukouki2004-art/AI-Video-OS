import pytest
from apps.api.workflow.context import WorkflowContext, VariableResolver

def test_variable_resolver_resolve_to_any_list():
    context = WorkflowContext()
    data = ["item1", "item2", "item3"]
    context.set_step_output("step1", data)
    
    resolver = VariableResolver(context)
    resolved = resolver.resolve_to_any("{{step1.output}}")
    
    assert resolved == data
    assert isinstance(resolved, list)

def test_variable_resolver_resolve_to_any_string_interpolation():
    context = WorkflowContext()
    context.set_step_output("step1", "val1")
    
    resolver = VariableResolver(context)
    resolved = resolver.resolve_to_any("Prefix: {{step1.output}}")
    
    assert resolved == "Prefix: val1"

def test_variable_resolver_loop_variable_resolution():
    context = WorkflowContext()
    context.set_step_output("item", "current_val")
    
    resolver = VariableResolver(context)
    resolved = resolver.resolve("Processing {{item}}")
    
    assert resolved == "Processing current_val"

def test_variable_resolver_resolve_to_any_unresolved_error():
    context = WorkflowContext()
    resolver = VariableResolver(context)
    
    with pytest.raises(ValueError, match="Unresolved variable"):
        resolver.resolve_to_any("{{missing.output}}")
