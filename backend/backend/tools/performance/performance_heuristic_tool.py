from __future__ import annotations

import ast
from typing import Any

from backend.tools.base import Tool


class _LoopVisitor(ast.NodeVisitor):
    def __init__(self, added_lines: set[int]) -> None:
        self.added_lines = added_lines
        self.findings: list[dict] = []
        self._loop_depth = 0

    def _touches_added(self, node: ast.AST) -> bool:
        start = getattr(node, "lineno", None)
        if start is None:
            return False
        end = getattr(node, "end_lineno", start) or start
        return any(start <= ln <= end for ln in self.added_lines)

    def _visit_loop(self, node: ast.For | ast.While) -> None:
        self._loop_depth += 1
        if self._loop_depth >= 2 and self._touches_added(node):
            self.findings.append(
                {
                    "lineno": node.lineno,
                    "type": "nested_loop",
                    "message": (
                        f"Loop at line {node.lineno} is nested inside another loop, which risks "
                        "O(n^2)+ time complexity as input size grows."
                    ),
                }
            )
        for child in ast.iter_child_nodes(node):
            self.visit(child)
        self._loop_depth -= 1

    def visit_For(self, node: ast.For) -> None:
        self._visit_loop(node)

    def visit_While(self, node: ast.While) -> None:
        self._visit_loop(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if (
            self._loop_depth >= 1
            and isinstance(node.op, ast.Add)
            and isinstance(node.target, ast.Name)
            and self._touches_added(node)
        ):
            self.findings.append(
                {
                    "lineno": node.lineno,
                    "type": "accumulate_in_loop",
                    "message": (
                        f"'{node.target.id} += ...' inside a loop at line {node.lineno} reallocates the "
                        "value on every iteration; if this accumulates a string or list, consider "
                        "list-append/str.join or a comprehension for large inputs."
                    ),
                }
            )
        self.generic_visit(node)


class PerformanceHeuristicTool(Tool):
    """Real Python AST analysis for common O(n^2)+ risk patterns: loops nested
    inside loops, and +=-accumulation inside a loop. A heuristic, not a
    profiler - flags patterns worth a closer look, doesn't measure actual cost."""

    name = "performance_heuristics"
    description = "Detect nested loops and in-loop accumulation patterns in diff-touched code."

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        source: str = input.get("source") or ""
        added_lines: set[int] = set(input.get("added_lines") or [])
        if not source:
            return {"performance_findings": []}

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {"performance_findings": []}

        visitor = _LoopVisitor(added_lines)
        visitor.visit(tree)
        return {"performance_findings": visitor.findings}
