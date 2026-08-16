from __future__ import annotations

import time

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.agent_result import AgentResult
from backend.core.agents.agent_support import AgentSupport
from backend.core.schemas.agent_state import ThinkingSummary


class OrchestratorAgent(AgentSupport):
    """The graph's entry node (spec §13.1). Does not perform analysis itself -
    it exists so the review's kickoff is visible in the UI as a real node/event,
    before GraphEngine fans out to Impact Analyzer and the parallel group."""

    name = "orchestrator"

    async def run(self, ctx: AgentContext) -> AgentResult:
        start = time.perf_counter()
        await self.emit_started(ctx)

        summary = ThinkingSummary(
            objective=f"Plan the review for PR #{ctx.pr.number} in {ctx.pr.repo}.",
            decision=f"{len(ctx.diff_files)} file(s) changed; routing to Impact Analyzer first.",
            action="Received webhook payload and diff-first PR context.",
            tool=None,
            observation="No prior review state to reuse for this PR.",
            next_action="Run Impact Analyzer, then fan out to Security/Bug/Test agents based on its result.",
        )
        await self.emit_thinking_summary(ctx, summary)

        duration_ms = int((time.perf_counter() - start) * 1000)
        await self.emit_completed(ctx, duration_ms=duration_ms)

        return AgentResult(
            agent_name=self.name,
            status=self.status,
            findings=[],
            summary=summary,
            duration_ms=duration_ms,
        )
