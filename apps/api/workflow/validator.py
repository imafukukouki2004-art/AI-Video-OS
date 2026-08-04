"""Validator for ensuring workflow definitions are structurally sound."""

import re
from typing import Any

from apps.api.domain.models import Workflow, WorkflowStep
from apps.api.domain.schemas import WorkflowValidationResult


class WorkflowValidator:
    """Validator for structural and logical consistency of workflows."""

    # Pattern: {{identifier.output}}, {{identifier.artifact}}, {{identifier.asset}},
    # {{identifier.image}} or {{variable}}
    VARIABLE_PATTERN = re.compile(
        r"\{\{\s*([\w\-\.]+?)(?:\.(output|artifact|asset|image))?\s*\}\}"
    )

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

        # 4. Reference and Syntax validation
        step_ids = {str(s.id) for s in steps}
        step_names = {s.name for s in steps}
        all_identifiers = step_ids | step_names

        condition_pattern = re.compile(r"^(.*?)\s*(==|!=)\s*\"(.*?)\"$")

        for step in steps:
            # Conditional branching validation
            if step.condition:
                # Syntax check
                if not condition_pattern.match(step.condition.strip()):
                    errors.append(
                        f"Step '{step.name}' has invalid condition syntax: {step.condition}"
                    )

                # Variable reference check in condition
                for var_match in self.VARIABLE_PATTERN.finditer(step.condition):
                    identifier = var_match.group(1)
                    if identifier not in all_identifiers and identifier != "item":
                        errors.append(
                            f"Step '{step.name}' references unknown step in condition: {identifier}"
                        )

                # Branch target check
                if step.next_step_on_true and str(step.next_step_on_true) not in step_ids:
                    errors.append(f"Step '{step.name}' has invalid next_step_on_true reference.")
                if step.next_step_on_false and str(step.next_step_on_false) not in step_ids:
                    errors.append(f"Step '{step.name}' has invalid next_step_on_false reference.")

            # Loop validation
            if step.loop_source:
                if not step.loop_variable:
                    errors.append(
                        f"Step '{step.name}' has loop_source but is missing loop_variable."
                    )
                if not self.VARIABLE_PATTERN.search(step.loop_source):
                    errors.append(
                        f"Step '{step.name}' has invalid loop_source (must be a variable)."
                    )
                else:
                    for var_match in self.VARIABLE_PATTERN.finditer(step.loop_source):
                        identifier = var_match.group(1)
                        if identifier not in all_identifiers:
                            errors.append(
                                f"Step '{step.name}' references unknown step in loop_source: "
                                f"{identifier}"
                            )

            # Step Config Variable Validation
            if step.config:
                self._validate_config_variables(step.name, step.config, all_identifiers, errors)

        # 5. Required fields check for each step
        for i, step in enumerate(steps):
            if not step.name:
                errors.append(f"Step at index {i} is missing a name.")
            if not step.step_type:
                errors.append(f"Step '{step.name or i}' is missing a step type.")
            if step.config is None:
                errors.append(f"Step '{step.name or i}' has null configuration.")

        return WorkflowValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def _validate_config_variables(
        self, step_name: str, config: dict[str, Any], all_identifiers: set[str], errors: list[str]
    ) -> None:
        def check_val(val: Any) -> None:
            if isinstance(val, str):
                for var_match in self.VARIABLE_PATTERN.finditer(val):
                    identifier = var_match.group(1)
                    if identifier not in all_identifiers and identifier != "item":
                        errors.append(f"Step '{step_name}' references unknown step: {identifier}")
            elif isinstance(val, dict):
                for v in val.values():
                    check_val(v)
            elif isinstance(val, list):
                for v in val:
                    check_val(v)

        for value in config.values():
            check_val(value)
