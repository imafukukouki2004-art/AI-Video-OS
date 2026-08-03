"""Condition evaluation for workflow branching."""

import re

from apps.api.workflow.context import VariableResolver


class ConditionEvaluator:
    """Evaluates simple string comparison conditions for workflow steps."""

    # Pattern: left_operand operator "right_operand"
    # Example: {{step1.output}} == "success"
    CONDITION_PATTERN = re.compile(r"^(.*?)\s*(==|!=)\s*\"(.*?)\"$")

    def __init__(self, resolver: VariableResolver) -> None:
        self.resolver = resolver

    def evaluate(self, condition_str: str) -> bool:
        """
        Evaluate a condition string.
        Returns True if the condition is met, False otherwise.
        Raises ValueError for invalid syntax or unresolved variables.
        """
        if not condition_str:
            return True

        match = self.CONDITION_PATTERN.match(condition_str.strip())
        if not match:
            raise ValueError(f"Invalid condition syntax: {condition_str}")

        left_raw, operator, right_value = match.groups()

        # Resolve variables in the left operand (e.g., {{step_id.output}})
        # VariableResolver.resolve returns a string
        left_value = self.resolver.resolve(left_raw.strip())

        if operator == "==":
            return left_value == right_value
        elif operator == "!=":
            return left_value != right_value

        return False
