from __future__ import annotations

import logging
from typing import Any

from backend.core.conditions.condition_types import DISPATCH
from backend.core.conditions.safe_evaluator import UnsafeExpressionError
from backend.core.schemas.edge import ConditionalEdge, EdgeEvaluationResult
from backend.core.utils import now_iso

logger = logging.getLogger(__name__)


def evaluate_edge(
    edge: ConditionalEdge,
    context: dict[str, Any],
    review_id: str,
    all_edges: list[ConditionalEdge] | None = None,
) -> EdgeEvaluationResult:
    """Deterministically evaluate a single conditional edge. Never calls an LLM (spec §10)."""
    if not edge.enabled:
        return EdgeEvaluationResult(
            edge_id=edge.edge_id,
            review_id=review_id,
            passed=False,
            value=None,
            reason="Edge disabled",
            evaluated_at=now_iso(),
        )

    strategy = DISPATCH.get(edge.condition_type)
    if strategy is None:
        return EdgeEvaluationResult(
            edge_id=edge.edge_id,
            review_id=review_id,
            passed=False,
            value=None,
            reason=f"Unknown condition type {edge.condition_type}",
            evaluated_at=now_iso(),
        )

    try:
        passed, value = strategy(edge, context, all_edges or [])
        reason = _describe(edge, value, passed)
    except UnsafeExpressionError as exc:
        logger.error("Unsafe condition on edge %s: %s", edge.edge_id, exc)
        passed, value, reason = False, None, f"Condition rejected: {exc}"

    return EdgeEvaluationResult(
        edge_id=edge.edge_id,
        review_id=review_id,
        passed=passed,
        value=value,
        reason=reason,
        evaluated_at=now_iso(),
    )


def _describe(edge: ConditionalEdge, value: Any, passed: bool) -> str:
    outcome = "TRUE" if passed else "FALSE"
    return f"[{edge.condition_type.value}] {edge.condition} evaluated to {value!r} -> {outcome}"
