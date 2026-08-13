import pytest

from apps.api.services.prompt_builder import PromptBuilder
from apps.api.workflow.context import VariableResolver, WorkflowContext


def test_prompt_builder_chain_uses_context_as_handoff() -> None:
    context = WorkflowContext()
    resolver = VariableResolver(context)
    builder = PromptBuilder()

    first = builder.build_from_config(
        {"prompt": "Generate a script"}, resolver, default_user_prompt="GenerateScript"
    )
    context.set_step_output("GenerateScript", "Opening scene")
    second = builder.build_from_config(
        {"prompt": "Rewrite {{GenerateScript.output}}"},
        resolver,
        default_user_prompt="RewriteScript",
    )
    context.set_step_output("RewriteScript", "A cinematic opening scene")
    third = builder.build_from_config(
        {"prompt": "Illustrate {{RewriteScript.output}}"},
        resolver,
        default_user_prompt="GenerateImage",
    )

    assert first.user_prompt == "Generate a script"
    assert second.user_prompt == "Rewrite Opening scene"
    assert third.user_prompt == "Illustrate A cinematic opening scene"


def test_prompt_chain_rejects_unpublished_step_output() -> None:
    resolver = VariableResolver(WorkflowContext())

    with pytest.raises(ValueError, match="Unresolved variable"):
        PromptBuilder().build_from_config(
            {"prompt": "Use {{FailedStep.output}}"},
            resolver,
            default_user_prompt="DownstreamStep",
        )
