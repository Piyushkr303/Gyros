from __future__ import annotations

import ast
from typing import Any


class UnsafeExpressionError(ValueError):
    """Raised when a condition expression uses a node type outside the safe whitelist."""


# Only these AST node types may appear anywhere in a condition expression.
_ALLOWED_NODE_TYPES = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Gt,
    ast.GtE,
    ast.Lt,
    ast.LtE,
    ast.Name,
    ast.Load,
    ast.Attribute,
    ast.Constant,
)


def _check_allowed(node: ast.AST) -> None:
    if not isinstance(node, _ALLOWED_NODE_TYPES):
        raise UnsafeExpressionError(f"Disallowed expression element: {type(node).__name__}")
    for child in ast.iter_child_nodes(node):
        _check_allowed(child)


def _resolve_name(node: ast.Name | ast.Attribute, context: dict[str, Any]) -> Any:
    """Resolve a bare Name or a single-level Attribute (Name.attr) against context.

    Deeper attribute chains (a.b.c) are rejected — only one level of dotted
    access is supported, matching AGENT_RESULT/TOOL_RESULT style conditions
    like `security_agent.findings_count`.
    """
    if isinstance(node, ast.Name):
        return context.get(node.id)
    if isinstance(node, ast.Attribute):
        if not isinstance(node.value, ast.Name):
            raise UnsafeExpressionError(
                "Only single-level attribute access is allowed (e.g. a.b, not a.b.c)"
            )
        base = context.get(node.value.id)
        if base is None:
            return None
        if isinstance(base, dict):
            return base.get(node.attr)
        return getattr(base, node.attr, None)
    raise UnsafeExpressionError(f"Cannot resolve node type {type(node).__name__}")


def _evaluate(node: ast.AST, context: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, context)

    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, (ast.Name, ast.Attribute)):
        return _resolve_name(node, context)

    if isinstance(node, ast.BoolOp):
        values = [_evaluate(v, context) for v in node.values]
        if isinstance(node.op, ast.And):
            result = True
            for v in values:
                result = result and bool(v)
            return result
        if isinstance(node.op, ast.Or):
            result = False
            for v in values:
                result = result or bool(v)
            return result
        raise UnsafeExpressionError(f"Unsupported boolean operator {type(node.op).__name__}")

    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return not bool(_evaluate(node.operand, context))
        raise UnsafeExpressionError(f"Unsupported unary operator {type(node.op).__name__}")

    if isinstance(node, ast.Compare):
        left = _evaluate(node.left, context)
        result = True
        for op, comparator_node in zip(node.ops, node.comparators, strict=True):
            right = _evaluate(comparator_node, context)
            result = result and _apply_comparator(op, left, right)
            left = right
        return result

    raise UnsafeExpressionError(f"Unsupported expression node {type(node).__name__}")


def _apply_comparator(op: ast.cmpop, left: Any, right: Any) -> bool:
    # Normalize case-insensitive string comparisons for enum-like values (e.g. "high" vs "HIGH").
    if isinstance(left, str) and isinstance(right, str):
        left, right = left.upper(), right.upper()

    if isinstance(op, ast.Eq):
        return left == right
    if isinstance(op, ast.NotEq):
        return left != right

    if left is None or right is None:
        return False

    if isinstance(op, ast.Gt):
        return left > right
    if isinstance(op, ast.GtE):
        return left >= right
    if isinstance(op, ast.Lt):
        return left < right
    if isinstance(op, ast.LtE):
        return left <= right

    raise UnsafeExpressionError(f"Unsupported comparator {type(op).__name__}")


def safe_eval(expr: str, context: dict[str, Any]) -> Any:
    """Safely evaluate a boolean condition expression against a context dict.

    Never uses eval()/exec()/compile-then-eval. Parses the expression to an
    AST, verifies every node is on a small whitelist, then walks the tree
    with a hand-written interpreter. Anything outside the whitelist -
    function calls, subscripts, lambdas, imports, multi-level attribute
    chains, etc. - raises UnsafeExpressionError before any evaluation occurs.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise UnsafeExpressionError(f"Invalid condition syntax: {expr!r}") from exc

    _check_allowed(tree)
    return _evaluate(tree, context)
