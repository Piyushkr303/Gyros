from __future__ import annotations

import ast
from typing import Any

from backend.tools.base import Tool

_CRITICAL_ACTION_KEYWORDS = (
    "payment",
    "charge",
    "refund",
    "transfer",
    "delete",
    "authorize",
    "withdraw",
)


def _is_log_call(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in ("debug", "info", "warning", "warn", "error", "exception", "critical")
    )


class _FunctionVisitor(ast.NodeVisitor):
    def __init__(self, added_lines: set[int]) -> None:
        self.added_lines = added_lines
        self.findings: list[dict] = []

    def _touches_added(self, node: ast.AST) -> bool:
        start = getattr(node, "lineno", None)
        if start is None:
            return False
        end = getattr(node, "end_lineno", start) or start
        return any(start <= ln <= end for ln in self.added_lines)

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if not self._touches_added(node):
            return

        has_log_call = any(_is_log_call(n) for n in ast.walk(node) if isinstance(n, ast.Call))
        is_critical_action = any(k in node.name.lower() for k in _CRITICAL_ACTION_KEYWORDS)
        if is_critical_action and not has_log_call:
            self.findings.append(
                {
                    "lineno": node.lineno,
                    "type": "no_audit_logging",
                    "message": (
                        f"Function '{node.name}' performs a critical action but has no logging call at all, "
                        "leaving no audit trail if it runs (or fails) in production."
                    ),
                }
            )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if self._touches_added(node):
            has_log = any(_is_log_call(n) for n in ast.walk(node) if isinstance(n, ast.Call))
            has_reraise = any(isinstance(n, ast.Raise) for n in node.body)
            if not has_log and not has_reraise:
                self.findings.append(
                    {
                        "lineno": node.lineno,
                        "type": "silent_exception_swallowed",
                        "message": (
                            f"except block at line {node.lineno} neither logs nor re-raises the exception, "
                            "silently swallowing failures with no way to observe them in production."
                        ),
                    }
                )
        self.generic_visit(node)


class ObservabilityHeuristicTool(Tool):
    """Real Python AST analysis: flags diff-touched critical-action functions
    with zero logging calls (no audit trail), and except blocks that neither
    log nor re-raise (silent failure)."""

    name = "observability_heuristics"
    description = (
        "Detect missing audit-trail logging and silently-swallowed exceptions in diff-touched code."
    )

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        source: str = input.get("source") or ""
        added_lines: set[int] = set(input.get("added_lines") or [])
        if not source:
            return {"observability_findings": []}

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {"observability_findings": []}

        visitor = _FunctionVisitor(added_lines)
        visitor.visit(tree)
        return {"observability_findings": visitor.findings}
