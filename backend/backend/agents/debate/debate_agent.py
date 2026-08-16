from __future__ import annotations

import json
import time

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.agent_result import AgentResult
from backend.core.agents.agent_support import AgentSupport
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.events import EventType
from backend.core.schemas.finding import Finding, Severity
from backend.core.schemas.message import MessageType
from backend.core.utils import now_iso
from backend.llm.base.provider import ChatMessage

_SEVERITY_VALUES = {s.value for s in Severity}


class DebateAgent(AgentSupport):
    """LLM-mediated resolution of the genuine severity conflicts Conflict
    Resolver Agent surfaces (spec: multi-agent debate). Conflict Resolver
    already does the deterministic, factual part - which findings overlap
    in location and disagree on severity; this agent's only job is the
    judgment call Conflict Resolver deliberately declines to make: is this
    the SAME issue seen at two severities (worth reconciling), or two
    genuinely DIFFERENT issues that just happen to be nearby (nothing to
    resolve)? Runs once per conflicting cluster, after Conflict Resolver and
    before Final Review; skips the LLM entirely (an avoided call, not a
    missing feature) when there's nothing to debate this run."""

    name = "debate_agent"

    async def run(
        self, ctx: AgentContext, findings: list[Finding], conflict_clusters: list[list[str]]
    ) -> AgentResult:
        start = time.perf_counter()
        await self.emit_started(ctx)

        try:
            by_id = {f.id: f for f in findings}
            debates: list[dict] = []
            resolved_count = 0
            independent_count = 0
            tokens_used = 0
            llm_calls_made = 0

            if not conflict_clusters:
                await self.record_token_usage(
                    ctx,
                    input_tokens=0,
                    output_tokens=0,
                    avoided=True,
                    reason="Conflict Resolver found no genuine severity conflicts this run - nothing to debate",
                )

            for cluster_ids in conflict_clusters:
                cluster = [by_id[fid] for fid in cluster_ids if fid in by_id]
                if len(cluster) < 2:
                    continue

                await ctx.event_bus.publish(
                    ctx.review_id,
                    EventType.DEBATE_STARTED,
                    {
                        "finding_ids": cluster_ids,
                        "agents": sorted({f.detecting_agent for f in cluster}),
                    },
                )
                await self._exchange_positions(ctx, cluster)

                messages: list[ChatMessage] = [
                    {"role": "user", "content": self._build_prompt(cluster)}
                ]
                response = await ctx.llm.complete(
                    system=self._system_prompt(),
                    messages=messages,
                    max_tokens=ctx.token_budget.max_output_tokens,
                )
                llm_calls_made += 1
                tokens_used += response.input_tokens + response.output_tokens
                await self.record_token_usage(
                    ctx,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    avoided=False,
                    provider_mode=response.provider_mode,
                )

                resolution = self._parse_resolution(response.text)
                same_issue = bool(resolution.get("same_issue"))
                resolved_severity = resolution.get("resolved_severity")
                rationale = str(resolution.get("rationale") or "No rationale returned.")

                now = now_iso()
                for f in cluster:
                    if same_issue and resolved_severity in _SEVERITY_VALUES:
                        f.severity = Severity(resolved_severity)
                    f.debate_resolution = rationale
                    f.updated_at = now
                    await ctx.finding_store.update(f)
                    await ctx.event_bus.publish(
                        ctx.review_id,
                        EventType.FINDING_CRITICIZED,
                        {"finding": f.model_dump(mode="json")},
                    )

                if same_issue:
                    resolved_count += 1
                else:
                    independent_count += 1

                debates.append(
                    {
                        "finding_ids": cluster_ids,
                        "agents": sorted({f.detecting_agent for f in cluster}),
                        "same_issue": same_issue,
                        "resolved_severity": resolved_severity,
                        "rationale": rationale,
                    }
                )
                await ctx.event_bus.publish(ctx.review_id, EventType.DEBATE_RESOLVED, debates[-1])

            last_rationale = (
                debates[-1]["rationale"]
                if debates
                else "Conflict Resolver found no severity-conflicting clusters this run."
            )
            summary = ThinkingSummary(
                objective="Resolve genuine severity conflicts between agents via LLM-mediated arbitration.",
                decision=(
                    f"{len(debates)} conflict(s) debated: {resolved_count} reconciled to a single severity, "
                    f"{independent_count} confirmed as independent findings that just happen to be nearby."
                    if debates
                    else "No genuine conflicts to debate this run."
                ),
                action="Exchanged each side's evidence as AgentMessages, then asked an impartial arbiter whether the conflicting findings describe the same underlying issue.",
                tool="message exchange + LLM arbitration" if debates else "none (no conflicts)",
                observation=last_rationale,
                next_action="Proceed to Final Review.",
            )
            await self.emit_thinking_summary(ctx, summary)

            duration_ms = int((time.perf_counter() - start) * 1000)
            await self.emit_completed(ctx, debates=len(debates), duration_ms=duration_ms)

            return AgentResult(
                agent_name=self.name,
                status=self.status,
                findings=findings,
                summary=summary,
                tokens_used=tokens_used,
                llm_calls_made=llm_calls_made,
                llm_calls_avoided=1 if not conflict_clusters else 0,
                duration_ms=duration_ms,
                condition_context={
                    "debate_count": len(debates),
                    "resolved_count": resolved_count,
                    "independent_count": independent_count,
                },
            )
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - start) * 1000)
            await self.emit_failed(ctx, str(exc))
            return AgentResult(
                agent_name=self.name, status=self.status, error=str(exc), duration_ms=duration_ms
            )

    async def _exchange_positions(self, ctx: AgentContext, cluster: list[Finding]) -> None:
        """Real message-passing, visible in the Communication Feed: every
        pair of disagreeing agents in this cluster exchanges the other's
        finding as an AgentMessage before the arbiter call - the LLM isn't
        the only thing that "sees" both sides, the agents' own message
        history reflects the exchange too."""
        for f in cluster:
            for other in cluster:
                if other.detecting_agent == f.detecting_agent:
                    continue
                await ctx.message_bus.send(
                    review_id=ctx.review_id,
                    sender=other.detecting_agent,
                    receiver=f.detecting_agent,
                    type=MessageType.CRITIQUE,
                    summary=(
                        f"At {other.file}:{other.line}, I found '{other.title}' ({other.severity.value}). "
                        f"How does this compare to your '{f.title}' ({f.severity.value}) at the same location?"
                    ),
                    finding_id=other.id,
                    evidence_ids=other.evidence_ids,
                    confidence=other.confidence,
                )

    def _system_prompt(self) -> str:
        return (
            "You are the Debate Agent, an impartial arbiter in a multi-agent PR review system. "
            "Two or more specialized agents each raised a finding at the same code location but "
            "disagreed sharply on severity. Read every position and its evidence, then judge: are "
            "these describing the SAME underlying issue (in which case pick the single most "
            "justified severity), or are they genuinely DIFFERENT issues that merely happen to be "
            "nearby (in which case neither should be changed)? "
            'Respond ONLY with strict JSON: {"same_issue": bool, "resolved_severity": '
            '"LOW"|"MEDIUM"|"HIGH"|"CRITICAL"|null, "rationale": str, "confidence": float}. '
            "resolved_severity must be null when same_issue is false. Base your judgment only on "
            "the positions and evidence given below - never invent facts not present there."
        )

    def _build_prompt(self, cluster: list[Finding]) -> str:
        positions = [
            {
                "finding_id": f.id,
                "agent": f.detecting_agent,
                "category": f.category,
                "severity": f.severity.value,
                "title": f.title,
                "description": f.description,
                "confidence": f.confidence,
            }
            for f in cluster
        ]
        return f"Conflicting positions at the same code location:\n\nDEBATE_JSON:\n{json.dumps(positions)}"

    def _parse_resolution(self, llm_text: str) -> dict:
        try:
            payload = json.loads(llm_text)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass
        return {
            "same_issue": False,
            "resolved_severity": None,
            "rationale": "Could not parse arbiter response.",
        }
