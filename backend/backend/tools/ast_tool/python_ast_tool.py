from __future__ import annotations

import ast
from typing import Any

from backend.tools.base import Tool


class PythonAstTool(Tool):
    """Real Python AST analysis (not regex): functions, classes, imports, and
    which functions were actually touched by the diff's added lines, plus the
    calls made from within those touched functions."""

    name = "python_ast"
    description = (
        "Parse a Python file's AST to extract functions/classes/imports and diff-touched functions."
    )

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        filename: str = input["filename"]
        source: str = input.get("source") or ""
        added_lines: set[int] = set(input.get("added_lines") or [])

        if not source:
            return {
                "filename": filename,
                "parse_error": "no_source",
                "functions": [],
                "classes": [],
                "imports": [],
            }

        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError as exc:
            return {
                "filename": filename,
                "parse_error": str(exc),
                "functions": [],
                "classes": [],
                "imports": [],
            }

        functions: list[dict] = []
        classes: list[dict] = []
        imports: list[str] = []
        touched_functions: list[dict] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imports.extend(f"{module}.{alias.name}" for alias in node.names)
            elif isinstance(node, ast.ClassDef):
                classes.append(
                    {"name": node.name, "lineno": node.lineno, "end_lineno": node.end_lineno}
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start, end = node.lineno, node.end_lineno or node.lineno
                calls = sorted(
                    {
                        n.func.id
                        for n in ast.walk(node)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    }
                    | {
                        n.func.attr
                        for n in ast.walk(node)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    }
                )
                func_info = {
                    "name": node.name,
                    "lineno": start,
                    "end_lineno": end,
                    "calls": calls,
                    "has_docstring": ast.get_docstring(node) is not None,
                    "arg_count": len(node.args.args),
                }
                functions.append(func_info)
                if any(start <= ln <= end for ln in added_lines):
                    touched_functions.append(func_info)

        return {
            "filename": filename,
            "functions": functions,
            "classes": classes,
            "imports": sorted(set(imports)),
            "touched_functions": touched_functions,
        }
