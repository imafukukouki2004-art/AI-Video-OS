"""Workflow context management and variable resolution."""

import re
from typing import Any


class WorkflowContext:
    """Holds state and outputs for a single workflow execution."""

    def __init__(self) -> None:
        self._outputs: dict[str, Any] = {}

    def set_step_output(self, step_identifier: str, output: Any) -> None:
        """Store the output of a step, indexed by its identifier (ID or Name)."""
        self._outputs[step_identifier] = output

    def get_step_output(self, step_identifier: str) -> Any:
        """Retrieve the output of a step by its identifier."""
        return self._outputs.get(step_identifier)

    def get_all_outputs(self) -> dict[str, Any]:
        """Return all stored outputs."""
        return self._outputs.copy()


class VariableResolver:
    """Resolves variables in strings using the workflow context."""

    # Pattern: {{identifier.output}} or {{variable}}
    VARIABLE_PATTERN = re.compile(r"\{\{\s*([\w\-\.]+?)(?:\.output)?\s*\}\}")

    def __init__(self, context: WorkflowContext) -> None:
        self.context = context

    def resolve_to_any(self, text: str) -> Any:
        """
        Resolve a single variable to its original type (e.g., list, dict).
        Useful for evaluating loop sources.
        """
        if not text:
            return text

        # If it's a single variable like "{{step1.output}}", return the actual value
        match = self.VARIABLE_PATTERN.fullmatch(text.strip())
        if match:
            identifier = match.group(1)
            value = self.context.get_step_output(identifier)
            if value is None:
                raise ValueError(f"Unresolved variable: {text}")
            return value

        # Otherwise, resolve as string interpolation
        return self.resolve(text)

    def resolve(self, text: str) -> str:
        """
        Replace all occurrences of {{step_id.output}} with actual values from context.
        Raises ValueError if a variable cannot be resolved.
        """
        if not text:
            return text

        def replace_match(match: re.Match[str]) -> str:
            identifier = match.group(1)
            value = self.context.get_step_output(identifier)

            if value is None:
                raise ValueError(f"Unresolved variable: {match.group(0)}")

            return str(value)

        try:
            return self.VARIABLE_PATTERN.sub(replace_match, text)
        except ValueError as e:
            # Re-raise to be caught by the runtime's error handling
            raise e
