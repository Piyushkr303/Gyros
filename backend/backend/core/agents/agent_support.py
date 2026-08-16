from __future__ import annotations

from backend.core.agents.agent_context import AgentContext
from backend.core.schemas.agent_state import AgentStatus
from backend.core.schemas.events import EventType
from backend.core.schemas.token_usage import TokenUsageRecord
from backend.core.schemas.tool import ToolResult
from backend.core.utils import new_id, now_iso
from backend.integrations.chaos import ChaosInjectedError
from backend.tools.base import Tool


class AgentSupport:
    """Shared event-emission helpers for anything acting as a node in the
    graph. BaseAgent (discovery agents) and the judgment agents
    (Validator/Critic/FinalReview, whose job is to re-process existing
    findings rather than discover new ones from a diff) both build on this
    instead of duplicating tool-call/token-usage plumbing."""

    name: str

    def __init__(self) -> None:
        self.status = AgentStatus.IDLE

    async def call_tool(self, ctx: AgentContext, tool: Tool, input: dict) -> ToolResult:
        self.status = AgentStatus.CALLING_TOOL
        await ctx.event_bus.publish(
            ctx.review_id, EventType.AGENT_TOOL_STARTED, {"agent": self.name, "tool": tool.name}
        )

        cached = await ctx.tool_cache.get(tool.name, input) if ctx.tool_cache else None
        if cached is not None:
            result = cached
            await ctx.event_bus.publish(
                ctx.review_id,
                EventType.TOOL_RESULT_CACHE_HIT,
                {"agent": self.name, "tool": tool.name},
            )
        else:
            result = await self._execute_with_chaos(ctx, tool, input)
            if ctx.tool_cache:
                await ctx.tool_cache.put(tool.name, input, result)

        await ctx.event_bus.publish(
            ctx.review_id,
            EventType.AGENT_TOOL_COMPLETED,
            {
                "agent": self.name,
                "tool": tool.name,
                "success": result.success,
                "duration_ms": result.duration_ms,
                "error": result.error,
                "from_cache": cached is not None,
            },
        )
        self.status = AgentStatus.RUNNING
        return result

    async def _execute_with_chaos(self, ctx: AgentContext, tool: Tool, input: dict) -> ToolResult:
        checkpoint = f"{ctx.review_id}:{self.name}:{tool.name}"
        try:
            ctx.chaos.maybe_fail(checkpoint)
        except ChaosInjectedError as exc:
            await ctx.event_bus.publish(
                ctx.review_id,
                EventType.CHAOS_FAILURE_INJECTED,
                {"agent": self.name, "tool": tool.name, "error": str(exc)},
            )
            result = await tool.execute(input)
            await ctx.event_bus.publish(
                ctx.review_id,
                EventType.CHAOS_RETRY_SUCCEEDED,
                {"agent": self.name, "tool": tool.name},
            )
            return result
        return await tool.execute(input)

    async def record_token_usage(
        self,
        ctx: AgentContext,
        *,
        input_tokens: int,
        output_tokens: int,
        avoided: bool,
        reason: str | None = None,
        provider_mode: str = "mock",
    ) -> None:
        record = TokenUsageRecord(
            id=new_id("tok"),
            review_id=ctx.review_id,
            agent=self.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=None,
            llm_call_avoided=avoided,
            avoided_reason=reason if avoided else None,
            provider_mode=provider_mode,
            timestamp=now_iso(),
        )
        await ctx.token_usage_repository.add(record)
        await ctx.event_bus.publish(
            ctx.review_id, EventType.TOKEN_USAGE_RECORDED, {"record": record.model_dump()}
        )

    async def emit_started(self, ctx: AgentContext) -> None:
        self.status = AgentStatus.RUNNING
        await ctx.event_bus.publish(ctx.review_id, EventType.AGENT_STARTED, {"agent": self.name})

    async def emit_completed(self, ctx: AgentContext, **payload) -> None:
        self.status = AgentStatus.COMPLETED
        await ctx.event_bus.publish(
            ctx.review_id, EventType.AGENT_COMPLETED, {"agent": self.name, **payload}
        )

    async def emit_failed(self, ctx: AgentContext, error: str) -> None:
        self.status = AgentStatus.FAILED
        await ctx.event_bus.publish(
            ctx.review_id, EventType.AGENT_FAILED, {"agent": self.name, "error": error}
        )

    async def emit_thinking_summary(self, ctx: AgentContext, summary) -> None:
        await ctx.event_bus.publish(
            ctx.review_id,
            EventType.AGENT_THINKING_SUMMARY,
            {"agent": self.name, "summary": summary.model_dump()},
        )
