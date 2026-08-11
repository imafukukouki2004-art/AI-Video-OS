import pytest
from pydantic import ValidationError

from apps.api.domain.prompt import PromptTemplate
from apps.api.services.prompt_builder import PromptBuilder
from apps.api.workflow.context import VariableResolver, WorkflowContext


def test_prompt_template_is_typed_and_immutable() -> None:
    template = PromptTemplate(template="  Explain {{topic}}  ", template_type="user")

    assert template.template == "Explain {{topic}}"
    with pytest.raises(ValidationError):
        template.template = "changed"


def test_prompt_builder_composes_system_and_user_prompts() -> None:
    context = WorkflowContext()
    context.set_variable("audience", "editors")
    context.set_step_output("research", "three verified facts")
    resolver = VariableResolver(context)

    composition = PromptBuilder().build_prompt(
        resolver,
        PromptTemplate(
            template="Write for {{audience}} using {{research.output}}.",
            template_type="user",
        ),
        PromptTemplate(template="Be concise for {{audience}}.", template_type="system"),
    )

    assert composition.user_prompt == "Write for editors using three verified facts."
    assert composition.system_prompt == "Be concise for editors."


def test_prompt_builder_supports_optional_system_prompt_and_existing_config() -> None:
    resolver = VariableResolver(WorkflowContext())

    composition = PromptBuilder().build_from_config(
        {"prompt": "Create a shot list", "temperature": 0.2},
        resolver,
        default_user_prompt="Fallback",
    )

    assert composition.user_prompt == "Create a shot list"
    assert composition.system_prompt is None


def test_prompt_builder_rejects_mismatched_template_roles() -> None:
    resolver = VariableResolver(WorkflowContext())

    with pytest.raises(ValueError, match="User prompt template"):
        PromptBuilder().build_prompt(
            resolver,
            PromptTemplate(template="Wrong role", template_type="system"),
        )
