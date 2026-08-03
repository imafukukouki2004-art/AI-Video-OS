"""Validator for ensuring workflow definitions are structurally sound."""

import re

from apps.api.domain.models import Workflow, WorkflowStep
from apps.api.domain.schemas import WorkflowValidationResult


class WorkflowValidator:
    """Validator for structural and logical consistency of workflows."""

    async def validate(
        self, workflow: Workflow, steps: list[WorkflowStep]
    ) -> WorkflowValidationResult:
        """
        Perform structural validation on a workflow and its steps.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # 1. Workflow existence check
        if not workflow:
            errors.append("Workflow definition not found.")
            return WorkflowValidationResult(valid=False, errors=errors, warnings=warnings)

        # 2. Step existence check
        if not steps:
            errors.append("Workflow has no steps defined.")

        # 3. Step order consistency
        orders = [s.order for s in steps]
        if orders != sorted(orders):
            errors.append("Workflow steps are not in correct sequential order.")

        if len(set(orders)) != len(orders):
            errors.append("Workflow contains duplicate step order indices.")

        # 4. Conditional branching validation
        step_ids = {s.id for s in steps}
        condition_pattern = re.compile(r"^(.*?)\s*(==|!=)\s*\"(.*?)\"$")

        for step in steps:
            if step.condition:
                # Syntax check
                if not condition_pattern.match(step.condition.strip()):
                    errors.append(
                        f"Step '{step.name}' has invalid condition syntax: {step.condition}"
                    )

                # Reference check
                if step.next_step_on_true and step.next_step_on_true not in step_ids:
                    errors.append(f"Step '{step.name}' has invalid next_step_on_true reference.")
                if step.next_step_on_false and step.next_step_on_false not in step_ids:
                    errors.append(f"Step '{step.name}' has invalid next_step_on_false reference.")

        # 5. Required fields check for each step
        for i, step in enumerate(steps):
            if not step.name:
                errors.append(f"Step at index {i} is missing a name.")
            if not step.step_type:
                errors.append(f"Step '{step.name or i}' is missing a step type.")
            if step.config is None:
                errors.append(f"Step '{step.name or i}' has null configuration.")

        return WorkflowValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)
