from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from backend.tools.base import Tool


class EslintTool(Tool):
    """Runs the real `eslint` linter against a plain JS/JSX file's content,
    if an `eslint` binary is available on PATH (e.g. `frontend/node_modules/
    .bin/eslint`, or a global install). Gracefully reports not-installed
    otherwise, same pattern as RuffTool/SemgrepTool/PylintTool.

    Deliberately scoped to `.jsx`, not `.tsx`: ESLint's default parser
    (espree) understands JSX syntax via ecmaFeatures but not TypeScript type
    annotations, and this project doesn't bundle @typescript-eslint/parser
    as a dependency just for this tool. `.tsx` stays covered by
    AccessibilityHeuristicTool's regex pass - claiming real TSX AST linting
    without the parser to back it would be dishonest, not just incomplete."""

    name = "eslint"
    description = "Run ESLint against changed plain JS/JSX file content."

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        filename: str = input["filename"]
        source: str = input.get("source") or ""

        binary = shutil.which("eslint") or shutil.which("eslint.cmd")
        if binary is None:
            return {"filename": filename, "installed": False, "violations": []}
        if not source:
            return {"filename": filename, "installed": True, "violations": []}

        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / Path(filename).name
            file_path.write_text(source, encoding="utf-8")

            proc = await asyncio.create_subprocess_exec(
                binary,
                "--no-eslintrc",
                "--env",
                "browser,es2021",
                "--parser-options=ecmaVersion:2021,sourceType:module,ecmaFeatures:{jsx:true}",
                "--rule",
                '{"no-undef": "off"}',
                "--format",
                "json",
                str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            try:
                raw_results = json.loads(stdout or b"[]")
            except json.JSONDecodeError:
                raw_results = []

            violations = [
                {
                    "rule": m.get("ruleId"),
                    "message": m.get("message"),
                    "lineno": m.get("line"),
                    "severity": "error" if m.get("severity") == 2 else "warning",
                }
                for r in raw_results
                for m in r.get("messages", [])
            ]
            return {"filename": filename, "installed": True, "violations": violations}
