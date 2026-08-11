"""Prompt composition service for workflow runtime execution."""

from collections.abc import Mapping
from typing import Any

from apps.api.domain.prompt import PromptComposition, PromptTemplate
from apps.api.workflow.context import VariableResolver


class PromptBuilder:
    """Resolve typed prompt templates against a workflow context."""

    def build_prompt(
        self,
        variable_resolver: VariableResolver,
        user_prompt_template: PromptTemplate,
        system_prompt_template: PromptTemplate | None = None,
    ) -> PromptComposition:
        """Compose provider-ready prompts while preserving their roles."""
        if user_prompt_template.template_type != "user":
            raise ValueError("User prompt template must have type 'user'")
        if system_prompt_template and system_prompt_template.template_type != "system":
            raise ValueError("System prompt template must have type 'system'")

        return PromptComposition(
            user_prompt=variable_resolver.resolve(user_prompt_template.template),
            system_prompt=(
                variable_resolver.resolve(system_prompt_template.template)
                if system_prompt_template
                else None
            ),
        )

    def build_from_config(
        self,
        config: Mapping[str, Any],
        variable_resolver: VariableResolver,
        *,
        default_user_prompt: str,
    ) -> PromptComposition:
        """Build prompts from the existing runtime configuration contract."""
        user_template = PromptTemplate(
            template=str(config.get("prompt") or default_user_prompt),
            template_type="user",
        )
        system_value = config.get("system_prompt")
        system_template = (
            PromptTemplate(template=str(system_value), template_type="system")
            if system_value is not None
            else None
        )
        return self.build_prompt(variable_resolver, user_template, system_template)
