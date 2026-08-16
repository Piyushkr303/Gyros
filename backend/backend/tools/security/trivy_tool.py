from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from backend.tools.base import Tool


class TrivyConfigTool(Tool):
    """Runs the real `trivy config` misconfiguration scanner against a
    changed Dockerfile/docker-compose file's content, if the `trivy` binary
    is available on PATH. Gracefully reports not-installed otherwise, same
    pattern as RuffTool/SemgrepTool/PylintTool/EslintTool.

    Deliberately scoped to `trivy config` (IaC misconfiguration rules
    against file *text*), not `trivy image`/`trivy fs` (built-image/
    filesystem vulnerability scanning): this project reviews PR diffs, not
    built container images, so config scanning is the mode that actually
    fits a diff-scoped model - the same reasoning that picked OSV over a
    full Trivy scan for dependency manifests (see osv_tool.py)."""

    name = "trivy_config"
    description = "Run `trivy config` against a changed Dockerfile/docker-compose file's content."

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        filename: str = input["filename"]
        source: str = input.get("source") or ""

        binary = shutil.which("trivy")
        if binary is None:
            return {"filename": filename, "installed": False, "violations": []}
        if not source:
            return {"filename": filename, "installed": True, "violations": []}

        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / Path(filename).name
            file_path.write_text(source, encoding="utf-8")

            proc = await asyncio.create_subprocess_exec(
                binary,
                "config",
                "--format",
                "json",
                "--quiet",
                str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            try:
                payload = json.loads(stdout or b"{}")
            except json.JSONDecodeError:
                payload = {}

            violations = [
                {
                    "id": m.get("ID"),
                    "title": m.get("Title"),
                    "message": m.get("Message"),
                    "severity": m.get("Severity"),
                    "lineno": (m.get("CauseMetadata") or {}).get("StartLine"),
                }
                for result in (payload.get("Results") or [])
                for m in (result.get("Misconfigurations") or [])
            ]
            return {"filename": filename, "installed": True, "violations": violations}
