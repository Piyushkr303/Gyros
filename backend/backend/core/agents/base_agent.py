from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.agent_result import AgentResult
from backend.core.agents.agent_support import AgentSupport
from backend.core.schemas.agent_state import AgentStatus, ThinkingSummary
from backend.core.schemas.events import EventType
from backend.core.schemas.finding import Finding
from backend.core.schemas.tool import ToolResult
from backend.llm.base.provider import ChatMessage

logger = logging.getLogger(__name__)


class BaseAgent(AgentSupport, ABC):
    """Template-method base class for discovery agents (Impact/Security/Bug/Test).

    Enforces the deterministic-first policy (spec §40.1): subclasses cannot
    skip run_deterministic_tools(), and needs_llm() is the single decision
    point for whether an LLM call happens at all. This is what makes
    `llm_call_avoided` tracking structural rather than a convention agents
    can forget to follow."""

    # --- subclass hooks -----------------------------------------------
    @abstractmethod
    async def run_deterministic_tools(self, ctx: AgentContext) -> list[ToolResult]:
        """Always runs first. Must never call the LLM."""

    @abstractmethod
    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        """(True, reason) if tool_results are inconclusive and LLM reasoning is
        required; otherwise (False, reason) explaining why deterministic
        evidence already answers the question."""

    @abstractmethod
    async def interpret(
        self,
        ctx: AgentContext,
        tool_results: list[ToolResult],
        llm_text: str | None,
    ) -> tuple[list[Finding], ThinkingSummary]:
        """Turn tool output (+ optional LLM JSON response) into Findings and a
        safe, structured ThinkingSummary (never raw chain-of-thought)."""

    def system_prompt(self) -> str:
        return (
            f"You are the {self.name}, a specialized software engineering review agent "
            "operating as part of a multi-agent PR review system. "
            "Respond ONLY with a strict JSON object of the shape: "
            '{"findings": [{"title": str, "description": str, '
            '"severity": "LOW"|"MEDIUM"|"HIGH"|"CRITICAL", "confidence": float, '
            '"file": str|null, "line": int|null, "evidence_ids": [str], '
            '"recommendation": str}], "reasoning": str}. '
            "Base your findings ONLY on the evidence provided below. "
            "Never invent files, line numbers, or facts not present in the evidence. "
            "If the evidence does not support a finding, return an empty findings list."
        )

    def condition_context(self, findings: list[Finding], tool_results: list[ToolResult]) -> dict:
        """Flattened view merged into GraphContext for downstream edge conditions."""
        return {"findings_count": len(findings)}

    # --- template method -------------------------------------------------
    async def run(self, ctx: AgentContext) -> AgentResult:
        start = time.perf_counter()
        await self.emit_started(ctx)

        try:
            tool_results = await self.run_deterministic_tools(ctx)
            needs_llm, reason = self.needs_llm(tool_results)

            llm_calls_made = 0
            llm_calls_avoided = 0
            tokens_used = 0
            llm_text: str | None = None

            if not needs_llm:
                llm_calls_avoided = 1
                await self.record_token_usage(
                    ctx, input_tokens=0, output_tokens=0, avoided=True, reason=reason
                )
            else:
                self.status = AgentStatus.THINKING_SUMMARY
                user_content = self._build_user_prompt(ctx)
                messages: list[ChatMessage] = [{"role": "user", "content": user_content}]
                response = await ctx.llm.complete(
                    system=self.system_prompt(),
                    messages=messages,
                    max_tokens=ctx.token_budget.max_output_tokens,
                )
                llm_text = response.text
                llm_calls_made = 1
                tokens_used = response.input_tokens + response.output_tokens
                await self.record_token_usage(
                    ctx,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    avoided=False,
                    provider_mode=response.provider_mode,
                )
                self.status = AgentStatus.RUNNING

            findings, summary = await self.interpret(ctx, tool_results, llm_text)
            await self.emit_thinking_summary(ctx, summary)

            for finding in findings:
                await ctx.finding_store.add(finding)
                await ctx.event_bus.publish(
                    ctx.review_id,
                    EventType.FINDING_CREATED,
                    {"finding": finding.model_dump(mode="json")},
                )

            duration_ms = int((time.perf_counter() - start) * 1000)
            await self.emit_completed(ctx, findings=len(findings), duration_ms=duration_ms)
            ctx.tracing.log_agent_span(
                ctx.trace,
                agent_name=self.name,
                input_summary={"tool_results": len(tool_results)},
                output_summary={"findings": len(findings)},
                llm_call_made=llm_calls_made > 0,
                duration_ms=duration_ms,
            )

            return AgentResult(
                agent_name=self.name,
                status=self.status,
                findings=findings,
                summary=summary,
                tokens_used=tokens_used,
                llm_calls_made=llm_calls_made,
                llm_calls_avoided=llm_calls_avoided,
                duration_ms=duration_ms,
                condition_context=self.condition_context(findings, tool_results),
            )
        except Exception as exc:
            logger.exception("Agent %s failed", self.name)
            duration_ms = int((time.perf_counter() - start) * 1000)
            await self.emit_failed(ctx, str(exc))
            ctx.tracing.log_agent_span(
                ctx.trace,
                agent_name=self.name,
                input_summary={},
                output_summary={"error": str(exc)},
                llm_call_made=False,
                duration_ms=duration_ms,
            )
            return AgentResult(
                agent_name=self.name,
                status=self.status,
                error=str(exc),
                duration_ms=duration_ms,
            )

    # --- helpers -----------------------------------------------------
    def _build_user_prompt(self, ctx: AgentContext) -> str:
        # By this point run_deterministic_tools() has already written every
        # tool finding into the shared EvidenceStore (with real evidence_ids) -
        # we query it back rather than re-deriving evidence from raw tool output,
        # so the LLM (real or mock) only ever sees evidence that was actually
        # produced deterministically and is independently queryable/citable.
        evidence = [
            {
                "evidence_id": e.evidence_id,
                "file": e.file,
                "line": e.line,
                "result": e.result,
                "confidence": e.confidence,
                "source": e.source,
            }
            for e in ctx.evidence_store.query(ctx.review_id, agent=self.name)
        ]
        return (
            "Deterministic tool evidence collected for this PR change:\n\n"
            f"EVIDENCE_JSON:\n{json.dumps(evidence)}"
        )
