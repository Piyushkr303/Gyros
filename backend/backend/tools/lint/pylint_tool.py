from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from backend.tools.base import Tool


class PylintTool(Tool):
    """Runs the real `pylint` static analyzer against a Python file's content,
    if the `pylint` binary is available on PATH. Gracefully reports
    not-installed otherwise rather than failing the agent. Distinct rule
    surface from ruff (convention/design-smell checks like too-many-branches,
    too-many-arguments, broad-except), not a duplicate of the Bug Detection
    Agent's ruff pass."""

    name = "pylint"
    description = "Run pylint (Python static analyzer) against changed file content."

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        filename: str = input["filename"]
        source: str = input.get("source") or ""

        binary = shutil.which("pylint")
        if binary is None:
            return {"filename": filename, "installed": False, "violations": []}
        if not source:
            return {"filename": filename, "installed": True, "violations": []}

        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / Path(filename).name
            file_path.write_text(source, encoding="utf-8")

            proc = await asyncio.create_subprocess_exec(
                binary,
                "--output-format=json",
                "--disable=C0114,C0115,C0116",  # missing docstrings - Documentation Agent's job, not this one
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
                    "symbol": v.get("symbol"),
                    "message": v.get("message"),
                    "lineno": v.get("line"),
                    "type": v.get("type"),
                }
                for v in raw_violations
                if v.get("type") in ("error", "warning", "refactor")
            ]
            return {"filename": filename, "installed": True, "violations": violations}
