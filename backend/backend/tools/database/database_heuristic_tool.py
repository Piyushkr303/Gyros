from __future__ import annotations

import re
from typing import Any

from backend.tools.base import Tool

_ADD_COLUMN_NOT_NULL_NO_DEFAULT = re.compile(
    r"ADD\s+COLUMN\s+\w+\s+[\w()]+\s+NOT\s+NULL(?!.*\bDEFAULT\b)", re.IGNORECASE
)
_ROLLBACK_MARKERS = ("-- down", "-- rollback", "-- revert")


class DatabaseHeuristicTool(Tool):
    """Deterministic regex heuristics over .sql migration files: flags a
    NOT NULL column added with no DEFAULT (breaks migration against existing
    rows) and migrations with no documented rollback/down section."""

    name = "database_heuristics"
    description = "Scan migration SQL for unsafe NOT NULL additions and missing rollback plans."

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        filename: str = input["filename"]
        source: str = input.get("source") or ""
        if not source:
            return {"database_findings": []}

        findings: list[dict] = []
        lines = source.splitlines()
        lowered = source.lower()

        for i, line in enumerate(lines, start=1):
            if _ADD_COLUMN_NOT_NULL_NO_DEFAULT.search(line):
                findings.append(
                    {
                        "lineno": i,
                        "type": "unsafe_not_null_migration",
                        "message": (
                            f"Line {i} adds a NOT NULL column with no DEFAULT, which will fail against "
                            "any existing rows when this migration runs."
                        ),
                    }
                )

        if not any(marker in lowered for marker in _ROLLBACK_MARKERS):
            findings.append(
                {
                    "lineno": 1,
                    "type": "missing_rollback",
                    "message": (
                        f"{filename} has no documented rollback/down section "
                        "(expected a '-- down' or '-- rollback' comment block)."
                    ),
                }
            )

        return {"database_findings": findings}
