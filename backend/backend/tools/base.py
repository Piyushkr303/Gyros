from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from backend.core.schemas.tool import ToolResult


class Tool(ABC):
    name: str
    description: str

    @abstractmethod
    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        """Subclasses implement the actual work and return `data` for ToolResult."""

    async def execute(self, input: dict[str, Any]) -> ToolResult:
        start = time.perf_counter()
        try:
            data = await self._run(input)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return ToolResult(success=True, tool_name=self.name, data=data, duration_ms=duration_ms)
        except Exception as exc:  # noqa: BLE001 - tool failures must surface as ToolResult, not crash agents
            duration_ms = int((time.perf_counter() - start) * 1000)
            return ToolResult(
                success=False,
                tool_name=self.name,
                data={},
                error=str(exc),
                duration_ms=duration_ms,
            )
