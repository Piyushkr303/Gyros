from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

from backend.tools.base import Tool


class PytestTool(Tool):
    """Actually runs pytest, but only against an isolated temp copy of the
    provided file contents - never the PR author's arbitrary code on the host
    directly (spec §84) - and only when explicitly enabled via
    ENABLE_TEST_EXECUTION. Writes files into a throwaway temp directory,
    invokes pytest --json-report there, and parses the summary."""

    name = "pytest_runner"
    description = "Execute pytest against an isolated temp checkout of provided file contents."

    def __init__(self, enabled: bool) -> None:
        self._enabled = enabled

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        if not self._enabled:
            return {"executed": False, "reason": "ENABLE_TEST_EXECUTION is false"}

        files: dict[str, str] = input.get("files") or {}
        if not files:
            return {"executed": False, "reason": "no files provided"}

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for rel_path, content in files.items():
                target = tmp_path / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            report_path = tmp_path / "report.json"
            proc = await asyncio.create_subprocess_exec(
                "pytest",
                "--json-report",
                f"--json-report-file={report_path}",
                "-q",
                str(tmp_path),
                cwd=str(tmp_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                await asyncio.wait_for(proc.communicate(), timeout=60)
            except TimeoutError:
                proc.kill()
                return {"executed": False, "reason": "pytest_timeout"}

            if not report_path.exists():
                return {"executed": False, "reason": "no_report_generated"}

            report = json.loads(report_path.read_text(encoding="utf-8"))
            summary = report.get("summary", {})
            failed_tests = [
                {"nodeid": t.get("nodeid"), "outcome": t.get("outcome")}
                for t in report.get("tests", [])
                if t.get("outcome") == "failed"
            ]

            return {
                "executed": True,
                "tests_found": summary.get("collected", 0),
                "tests_run": summary.get("total", 0),
                "tests_passed": summary.get("passed", 0),
                "tests_failed": summary.get("failed", 0),
                "failed_tests": failed_tests,
            }
