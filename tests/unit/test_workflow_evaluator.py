from unittest.mock import MagicMock

import pytest

from apps.api.workflow.evaluator import ConditionEvaluator


@pytest.fixture
def mock_resolver():
    resolver = MagicMock()

    # Mock resolution: {{step1.output}} -> "success"
    def side_effect(text):
        if "{{step1.output}}" in text:
            return "success"
        if "{{step2.output}}" in text:
            return "failure"
        raise ValueError(f"Unresolved variable: {text}")

    resolver.resolve.side_effect = side_effect
    return resolver


def test_condition_evaluator_equals_true(mock_resolver):
    evaluator = ConditionEvaluator(mock_resolver)
    assert evaluator.evaluate('{{step1.output}} == "success"') is True


def test_condition_evaluator_equals_false(mock_resolver):
    evaluator = ConditionEvaluator(mock_resolver)
    assert evaluator.evaluate('{{step1.output}} == "failure"') is False


def test_condition_evaluator_not_equals_true(mock_resolver):
    evaluator = ConditionEvaluator(mock_resolver)
    assert evaluator.evaluate('{{step1.output}} != "failure"') is True


def test_condition_evaluator_not_equals_false(mock_resolver):
    evaluator = ConditionEvaluator(mock_resolver)
    assert evaluator.evaluate('{{step1.output}} != "success"') is False


def test_condition_evaluator_invalid_syntax(mock_resolver):
    evaluator = ConditionEvaluator(mock_resolver)
    with pytest.raises(ValueError, match="Invalid condition syntax"):
        evaluator.evaluate('{{step1.output}} contains "success"')


def test_condition_evaluator_unresolved_variable(mock_resolver):
    evaluator = ConditionEvaluator(mock_resolver)
    with pytest.raises(ValueError, match="Unresolved variable"):
        evaluator.evaluate('{{missing.output}} == "any"')


def test_condition_evaluator_empty_condition(mock_resolver):
    evaluator = ConditionEvaluator(mock_resolver)
    assert evaluator.evaluate("") is True
    assert evaluator.evaluate(None) is True
