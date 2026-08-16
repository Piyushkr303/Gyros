from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from backend.tools.base import Tool


class RuffTool(Tool):
    """Runs the real `ruff` linter against a Python file's content, if the
    `ruff` binary is available on PATH. Gracefully reports not-installed
    otherwise rather than failing the agent."""

    name = "ruff"
    description = "Run ruff (Python linter) against changed file content."

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        filename: str = input["filename"]
        source: str = input.get("source") or ""

        binary = shutil.which("ruff")
        if binary is None:
            return {"filename": filename, "installed": False, "violations": []}
        if not source:
            return {"filename": filename, "installed": True, "violations": []}

        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / Path(filename).name
            file_path.write_text(source, encoding="utf-8")

            proc = await asyncio.create_subprocess_exec(
                binary,
                "check",
                "--output-format=json",
                "--no-cache",
                str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            try:
                raw_violations = json.loads(stdout or b"[]")
            except json.JSONDecodeError:
                raw_violations = []

            violations = [
                {
                    "code": v.get("code"),
                    "message": v.get("message"),
                    "lineno": (v.get("location") or {}).get("row"),
                }
                for v in raw_violations
            ]
            return {"filename": filename, "installed": True, "violations": violations}
