from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.core.conditions.safe_evaluator import safe_eval
from backend.core.schemas.edge import ConditionalEdge, ConditionType

# A strategy receives (edge, context, sibling_edges) and returns (passed, value).
ConditionStrategy = Callable[
    [ConditionalEdge, dict[str, Any], list[ConditionalEdge]], tuple[bool, Any]
]


def _always(
    edge: ConditionalEdge, context: dict[str, Any], siblings: list[ConditionalEdge]
) -> tuple[bool, Any]:
    return True, True


def _expression(
    edge: ConditionalEdge, context: dict[str, Any], siblings: list[ConditionalEdge]
) -> tuple[bool, Any]:
    value = safe_eval(edge.condition, context)
    return bool(value), value


def _else(
    edge: ConditionalEdge, context: dict[str, Any], siblings: list[ConditionalEdge]
) -> tuple[bool, Any]:
    sibling_if_edges = [
        s
        for s in siblings
        if s.source_agent == edge.source_agent and s.condition_type == ConditionType.IF
    ]
    any_sibling_true = any(bool(safe_eval(s.condition, context)) for s in sibling_if_edges)
    return (not any_sibling_true), (not any_sibling_true)


def _event(
    edge: ConditionalEdge, context: dict[str, Any], siblings: list[ConditionalEdge]
) -> tuple[bool, Any]:
    last_event = context.get("last_event") or {}
    actual = last_event.get("type")
    passed = actual == edge.condition
    return passed, actual


DISPATCH: dict[ConditionType, ConditionStrategy] = {
    ConditionType.ALWAYS: _always,
    ConditionType.IF: _expression,
    ConditionType.AND: _expression,
    ConditionType.OR: _expression,
    ConditionType.NOT: _expression,
    ConditionType.THRESHOLD: _expression,
    ConditionType.AGENT_RESULT: _expression,
    ConditionType.TOOL_RESULT: _expression,
    ConditionType.ELSE: _else,
    ConditionType.EVENT: _event,
}
