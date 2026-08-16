from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from backend.tools.base import Tool


class GitDiffTool(Tool):
    """Computes changed-file statistics directly from the GitHub PR file list
    (filenames, status, additions/deletions) - no full repository clone,
    honoring the diff-first strategy (spec §41)."""

    name = "git_diff"
    description = "Summarize changed-file statistics from a PR's file list."

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        files: list[dict] = input.get("files") or []

        by_extension: Counter[str] = Counter()
        total_additions = 0
        total_deletions = 0
        for f in files:
            ext = Path(f["filename"]).suffix.lstrip(".") or "none"
            by_extension[ext] += 1
            total_additions += f.get("additions", 0)
            total_deletions += f.get("deletions", 0)

        return {
            "total_files": len(files),
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "by_extension": dict(by_extension),
        }
