from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.core.persistence.models import ToolResultCacheRow
from backend.core.persistence.repositories import ToolResultCacheRepository
from backend.core.schemas.tool import ToolResult
from backend.core.utils import now_iso

# Tools whose output is a pure function of their input (file content /
# added-line text, not live review state) are safe to reuse across calls -
# re-running ruff/pylint/AST-parsing on file content this project has
# already analyzed once (e.g. an unchanged file re-seen on a later trigger,
# or a shared library file touched by two different PRs) is real avoidable
# work. Tools that talk to external/mutable state (GitHub file-fetch at
# HEAD, Jira, OSV's live vulnerability feed) are deliberately excluded -
# their answer can legitimately change between calls even for identical
# input, so caching them would risk silently serving stale data.
CACHEABLE_TOOLS = {
    "ruff",
    "semgrep",
    "pylint",
    "eslint",
    "python_ast",
    "regex_heuristics",
    "accessibility_heuristics",
    "performance_heuristics",
    "reliability_heuristics",
    "observability_heuristics",
    "dependency_heuristics",
    "database_heuristics",
    "test_static_heuristic",
    "diff_parser",
}


def _cache_key(tool_name: str, input: dict[str, Any]) -> str:
    payload = json.dumps(input, sort_keys=True, default=str)
    digest = hashlib.sha256(f"{tool_name}:{payload}".encode()).hexdigest()
    return f"{tool_name}:{digest}"


class ToolResultCache:
    """Real previous-result reuse (the spec's "context compression / cache
    beyond the basic evidence store" platform item): identical (tool, input)
    pairs skip re-execution and return the persisted prior ToolResult
    instead, surviving process restarts since it's SQLite-backed like
    everything else here. Scoped honestly to CACHEABLE_TOOLS - this is a
    deterministic-tool cache, not a general LLM-context-compression system,
    which this project doesn't need given deterministic-first tooling
    already keeps LLM calls rare."""

    def __init__(self, repo: ToolResultCacheRepository) -> None:
        self._repo = repo

    def is_cacheable(self, tool_name: str) -> bool:
        return tool_name in CACHEABLE_TOOLS

    async def get(self, tool_name: str, input: dict[str, Any]) -> ToolResult | None:
        if not self.is_cacheable(tool_name):
            return None
        row = await self._repo.get(_cache_key(tool_name, input))
        if row is None:
            return None
        await self._repo.increment_hit(row.cache_key)
        return ToolResult(
            success=row.success,
            tool_name=tool_name,
            data=row.data_json,
            error=row.error,
            duration_ms=0,
        )

    async def put(self, tool_name: str, input: dict[str, Any], result: ToolResult) -> None:
        if not self.is_cacheable(tool_name) or not result.success:
            return
        key = _cache_key(tool_name, input)
        if await self._repo.get(key) is not None:
            return
        await self._repo.add(
            ToolResultCacheRow(
                cache_key=key,
                tool_name=tool_name,
                success=result.success,
                data_json=result.data,
                error=result.error,
                created_at=now_iso(),
            )
        )
