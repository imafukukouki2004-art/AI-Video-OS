"""Workflow context management and variable resolution."""

import re
from typing import Any


class WorkflowContext:
    """Holds state, outputs, and artifact references for a single workflow execution."""

    def __init__(self) -> None:
        self._outputs: dict[str, Any] = {}
        self._artifacts: dict[str, Any] = {}
        self._assets: dict[str, Any] = {}
        self._images: dict[str, Any] = {}
        self._variables: dict[str, Any] = {}

    def set_step_output(self, step_identifier: str, output: Any) -> None:
        """Store the output of a step, indexed by its identifier (ID or Name)."""
        self._outputs[step_identifier] = output

    def get_step_output(self, step_identifier: str) -> Any:
        """Retrieve the output of a step by its identifier."""
        return self._outputs.get(step_identifier)

    def set_step_artifact(self, step_identifier: str, artifact: Any) -> None:
        """Store the artifact reference of a step."""
        self._artifacts[step_identifier] = artifact

    def get_step_artifact(self, step_identifier: str) -> Any:
        """Retrieve the artifact reference of a step."""
        return self._artifacts.get(step_identifier)

    def set_step_asset(self, step_identifier: str, asset: Any) -> None:
        """Store the asset reference of a step."""
        self._assets[step_identifier] = asset

    def get_step_asset(self, step_identifier: str) -> Any:
        """Retrieve the asset reference of a step."""
        return self._assets.get(step_identifier)

    def set_step_image(self, step_identifier: str, image_url: str) -> None:
        """Store the generated image URL of a step."""
        self._images[step_identifier] = image_url

    def get_step_image(self, step_identifier: str) -> Any:
        """Retrieve the generated image URL of a step."""
        return self._images.get(step_identifier)

    def set_variable(self, key: str, value: Any) -> None:
        """Store a generic variable in the context."""
        self._variables[key] = value

    def get_variable(self, key: str) -> Any:
        """Retrieve a generic variable from the context."""
        return self._variables.get(key)

    def get_all_outputs(self) -> dict[str, Any]:
        """Return all stored outputs."""
        return self._outputs.copy()


class VariableResolver:
    """Resolves variables in strings using the workflow context."""

    # Pattern: {{identifier.output}}, {{identifier.artifact}}, {{identifier.asset}},
    # {{identifier.image}} or {{variable}}
    VARIABLE_PATTERN = re.compile(r"\{\{\s*([\w\-\.]+?)(?:\.(output|artifact|asset|image))?\s*\}\}")

    def __init__(self, context: WorkflowContext) -> None:
        self.context = context

    def _resolve_value(self, identifier: str, suffix: str | None) -> Any:
        if suffix == "artifact":
            return self.context.get_step_artifact(identifier)
        if suffix == "asset":
            return self.context.get_step_asset(identifier)
        if suffix == "image":
            return self.context.get_step_image(identifier)
        if suffix == "output":
            return self.context.get_step_output(identifier)

        value = self.context.get_variable(identifier)
        if value is None:
            # Preserve the original loop-variable contract, which stored loop
            # values in the step-output namespace.
            value = self.context.get_step_output(identifier)
        return value

    def resolve_to_any(self, text: str) -> Any:
        """
        Resolve a single variable to its original type (e.g., list, dict, UUID).
        Useful for evaluating loop sources or artifact references.
        """
        if not text:
            return text

        # If it's a single variable like "{{step1.artifact}}", return the actual value
        match = self.VARIABLE_PATTERN.fullmatch(text.strip())
        if match:
            identifier = match.group(1)
            suffix = match.group(2)

            value = self._resolve_value(identifier, suffix)

            if value is None:
                raise ValueError(f"Unresolved variable: {text}")
            return value

        # Otherwise, resolve as string interpolation
        return self.resolve(text)

    def resolve(self, text: str) -> str:
        """
        Replace all occurrences of {{step_id.suffix}} with actual values from context.
        Raises ValueError if a variable cannot be resolved.
        """
        if not text:
            return text

        def replace_match(match: re.Match[str]) -> str:
            identifier = match.group(1)
            suffix = match.group(2)

            value = self._resolve_value(identifier, suffix)

            if value is None:
                raise ValueError(f"Unresolved variable: {match.group(0)}")

            return str(value)

        return self.VARIABLE_PATTERN.sub(replace_match, text)
