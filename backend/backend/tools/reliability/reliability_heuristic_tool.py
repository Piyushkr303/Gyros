from __future__ import annotations

import ast
from typing import Any

from backend.tools.base import Tool

_SIDE_EFFECT_KEYWORDS = (
    "record",
    "save",
    "write",
    "charge",
    "reverse",
    "commit",
    "delete",
    "send",
    "post",
    "publish",
)


class _FunctionVisitor(ast.NodeVisitor):
    def __init__(self, added_lines: set[int]) -> None:
        self.added_lines = added_lines
        self.findings: list[dict] = []

    def _check(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        start = node.lineno
        end = node.end_lineno or start
        if not any(start <= ln <= end for ln in self.added_lines):
            return

        has_try = any(isinstance(n, ast.Try) for n in ast.walk(node))
        if has_try:
            return

        risky_calls = sorted(
            {
                n.func.attr
                for n in ast.walk(node)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and any(k in n.func.attr.lower() for k in _SIDE_EFFECT_KEYWORDS)
            }
        )
        if risky_calls:
            self.findings.append(
                {
                    "lineno": start,
                    "type": "no_error_handling",
                    "message": (
                        f"Function '{node.name}' calls side-effecting method(s) {risky_calls} with no "
                        "try/except around them; a failure here will propagate uncaught."
                    ),
                }
            )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check(node)
        self.generic_visit(node)


class ReliabilityHeuristicTool(Tool):
    """Real Python AST analysis: flags diff-touched functions that call
    side-effecting methods (record/save/charge/send/etc.) with no surrounding
    try/except, so a downstream failure would propagate uncaught."""

    name = "reliability_heuristics"
    description = "Detect diff-touched functions with side-effecting calls and no error handling."

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        source: str = input.get("source") or ""
        added_lines: set[int] = set(input.get("added_lines") or [])
        if not source:
            return {"reliability_findings": []}

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {"reliability_findings": []}

        visitor = _FunctionVisitor(added_lines)
        visitor.visit(tree)
        return {"reliability_findings": visitor.findings}
