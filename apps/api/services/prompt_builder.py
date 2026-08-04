from typing import Any, Dict, List

from apps.api.domain.models.prompt import PromptTemplate
from apps.api.workflow.context import WorkflowContext
from apps.api.workflow.variable_resolver import VariableResolver


class PromptBuilder:
    def __init__(self):
        pass

    async def build_prompt(
        self,
        workflow_context: WorkflowContext,
        variable_resolver: VariableResolver,
        system_prompt_template: PromptTemplate,
        user_prompt_template: PromptTemplate,
    ) -> Dict[str, Any]:
        # Resolve variables in system prompt template
        resolved_system_prompt = variable_resolver.resolve(
            system_prompt_template.template
        )

        # Resolve variables in user prompt template
        resolved_user_prompt = variable_resolver.resolve(
            user_prompt_template.template
        )

        return {
            "system_prompt": resolved_system_prompt,
            "user_prompt": resolved_user_prompt,
        }

    async def load_template(self, template_id: UUID) -> PromptTemplate:
        # This is a placeholder. In a real implementation, this would load from a database or file system.
        # For now, we'll return a dummy template.
        if template_id == UUID("00000000-0000-0000-0000-000000000001"):
            return PromptTemplate(
                template="You are a helpful AI assistant.",
                template_type="system",
                description="Default system prompt",
            )
        elif template_id == UUID("00000000-0000-0000-0000-000000000002"):
            return PromptTemplate(
                template="Hello, {{user_name}}! What can I do for you today?",
                template_type="user",
                description="Default user prompt",
            )
        else:
            raise ValueError(f"Prompt template with ID {template_id} not found.")
