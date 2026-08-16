from __future__ import annotations

import ast
from typing import Any

from backend.tools.base import Tool


class TestStaticHeuristicTool(Tool):
    """Static, no-execution test analysis: counts existing test functions and
    naively correlates changed function names against test file contents to
    flag functions with no apparent test coverage."""

    name = "test_static_heuristic"
    description = "Static analysis of test files: test count and naive coverage correlation."

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        test_files: list[dict] = input.get("test_files") or []
        changed_function_names: list[str] = input.get("changed_function_names") or []

        test_names: list[str] = []
        combined_test_source = ""
        for tf in test_files:
            source = tf.get("source") or ""
            combined_test_source += "\n" + source
            try:
                tree = ast.parse(source, filename=tf.get("filename", "<test>"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and node.name.startswith("test_"):
                    test_names.append(node.name)

        covered = [fn for fn in changed_function_names if fn and fn in combined_test_source]
        uncovered = [fn for fn in changed_function_names if fn and fn not in combined_test_source]

        return {
            "tests_found": len(test_names),
            "test_names": test_names,
            "covered_functions": covered,
            "uncovered_functions": uncovered,
        }
