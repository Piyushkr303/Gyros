from __future__ import annotations

import json
import time

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.agent_result import AgentResult
from backend.core.agents.agent_support import AgentSupport
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.events import EventType
from backend.core.schemas.finding import CriticStatus, Finding, Severity, ValidationStatus
from backend.llm.base.provider import ChatMessage

_SEVERITY_ORDER = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}


class FinalReviewAgent(AgentSupport):
    """Aggregates CONFIRMED + ACCEPTED findings into the final review (spec §37).
    The finding fields themselves are already fully populated by upstream
    agents/Validator/Critic - this agent's only LLM use is an optional prose
    summary; the structured review content is entirely deterministic."""

    name = "final_review_agent"

    async def run(self, ctx: AgentContext, findings: list[Finding]) -> AgentResult:
        start = time.perf_counter()
        await self.emit_started(ctx)

        try:
            publishable = [
                f
                for f in findings
                if f.validator_status == ValidationStatus.CONFIRMED
                and f.critic_status == CriticStatus.ACCEPTED
            ]
            publishable.sort(key=lambda f: _SEVERITY_ORDER[f.severity], reverse=True)
            high_severity_count = sum(
                1
                for f in publishable
                if _SEVERITY_ORDER[f.severity] >= _SEVERITY_ORDER[Severity.HIGH]
            )

            llm_calls_made = 0
            llm_calls_avoided = 0
            tokens_used = 0

            if publishable:
                llm_calls_made = 1
                messages: list[ChatMessage] = [
                    {"role": "user", "content": self._build_prompt(publishable)}
                ]
                response = await ctx.llm.complete(
                    system=self._system_prompt(),
                    messages=messages,
                    max_tokens=ctx.token_budget.max_output_tokens,
                )
                tokens_used = response.input_tokens + response.output_tokens
                await self.record_token_usage(
                    ctx,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    avoided=False,
                    provider_mode=response.provider_mode,
                )
                review_summary = self._parse_summary(response.text, publishable)
            else:
                llm_calls_avoided = 1
                await self.record_token_usage(
                    ctx,
                    input_tokens=0,
                    output_tokens=0,
                    avoided=True,
                    reason="No publishable findings to summarize",
                )
                review_summary = "No confirmed, accepted findings were produced for this PR."

            await ctx.event_bus.publish(
                ctx.review_id,
                EventType.REVIEW_GENERATED,
                {
                    "summary": review_summary,
                    "findings": [f.model_dump(mode="json") for f in publishable],
                    "high_severity_count": high_severity_count,
                },
            )

            summary = ThinkingSummary(
                objective="Compile the final review from confirmed and accepted findings.",
                decision=f"{len(publishable)} finding(s) are publishable ({high_severity_count} at HIGH+ severity).",
                action="Filtered findings to CONFIRMED validator status and ACCEPTED critic status, sorted by severity.",
                tool="deterministic aggregation" + (" + LLM prose summary" if publishable else ""),
                observation=review_summary,
                next_action="Await human approval before publishing to GitHub.",
            )
            await self.emit_thinking_summary(ctx, summary)

            duration_ms = int((time.perf_counter() - start) * 1000)
            await self.emit_completed(ctx, publishable=len(publishable), duration_ms=duration_ms)

            return AgentResult(
                agent_name=self.name,
                status=self.status,
                findings=publishable,
                summary=summary,
                tokens_used=tokens_used,
                llm_calls_made=llm_calls_made,
                llm_calls_avoided=llm_calls_avoided,
                duration_ms=duration_ms,
                condition_context={
                    "publishable_count": len(publishable),
                    "high_severity_count": high_severity_count,
                    "review_summary": review_summary,
                },
            )
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - start) * 1000)
            await self.emit_failed(ctx, str(exc))
            return AgentResult(
                agent_name=self.name, status=self.status, error=str(exc), duration_ms=duration_ms
            )

    def _system_prompt(self) -> str:
        return (
            "You are the Final Review Agent. Respond ONLY with strict JSON: "
            '{"summary": str, "reasoning": str}. Write a concise 2-4 sentence prose '
            "summary of the confirmed findings provided. Do not invent findings not listed."
        )

    def _build_prompt(self, publishable: list[Finding]) -> str:
        items = [
            {"title": f.title, "severity": f.severity.value, "file": f.file} for f in publishable
        ]
        return f"Confirmed, accepted findings for this PR:\n\nSUMMARY_JSON:\n{json.dumps(items)}"

    def _parse_summary(self, llm_text: str, publishable: list[Finding]) -> str:
        try:
            payload = json.loads(llm_text)
            summary = payload.get("summary")
            if summary:
                return str(summary)
        except json.JSONDecodeError:
            pass
        titles = ", ".join(f.title for f in publishable[:3])
        return f"{len(publishable)} confirmed finding(s), including: {titles}"
