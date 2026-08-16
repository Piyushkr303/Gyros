from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from backend.tools.base import Tool


class SemgrepTool(Tool):
    """Runs `semgrep --config auto` against a file if the binary is
    available. Gracefully reports not-installed otherwise so agents can fall
    back to RegexHeuristicTool without failing."""

    name = "semgrep"
    description = "Run semgrep security static analysis against changed file content."

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        filename: str = input["filename"]
        source: str = input.get("source") or ""

        binary = shutil.which("semgrep")
        if binary is None:
            return {"filename": filename, "installed": False, "results": []}
        if not source:
            return {"filename": filename, "installed": True, "results": []}

        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / Path(filename).name
            file_path.write_text(source, encoding="utf-8")

            proc = await asyncio.create_subprocess_exec(
                binary,
                "--config",
                "auto",
                "--json",
                "--quiet",
                str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            except TimeoutError:
                proc.kill()
                return {
                    "filename": filename,
                    "installed": True,
                    "results": [],
                    "error": "semgrep_timeout",
                }

            try:
                payload = json.loads(stdout or b"{}")
            except json.JSONDecodeError:
                payload = {}

            results = [
                {
                    "check_id": r.get("check_id"),
                    "message": (r.get("extra") or {}).get("message"),
                    "severity": (r.get("extra") or {}).get("severity"),
                    "lineno": (r.get("start") or {}).get("line"),
                }
                for r in payload.get("results", [])
            ]
            return {"filename": filename, "installed": True, "results": results}
