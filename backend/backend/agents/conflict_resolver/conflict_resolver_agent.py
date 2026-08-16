from __future__ import annotations

import time
from collections import defaultdict

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.agent_result import AgentResult
from backend.core.agents.agent_support import AgentSupport
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.events import EventType
from backend.core.schemas.finding import Finding, Severity, ValidationStatus
from backend.core.utils import now_iso

_SEVERITY_ORDER = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}
_LINE_WINDOW = 3
_CONFLICT_SEVERITY_GAP = 2


class ConflictResolverAgent(AgentSupport):
    """Cross-references findings from different agents that land on
    overlapping file:line locations - a deterministic, always-runs-after-
    Critic synthesis step (spec-style multi-agent disagreement resolution).
    Purely mechanical clustering by (file, line-window): it never calls the
    LLM, since detecting *which* agents overlap is a fact, not a judgment
    call. Annotates each finding's `impact` field with the cross-reference;
    the human reviewer makes the final call on genuine severity conflicts,
    this agent only surfaces them."""

    name = "conflict_resolver_agent"

    async def run(self, ctx: AgentContext, findings: list[Finding]) -> AgentResult:
        start = time.perf_counter()
        await self.emit_started(ctx)

        try:
            candidates = [f for f in findings if f.validator_status == ValidationStatus.CONFIRMED]
            by_file: dict[str, list[Finding]] = defaultdict(list)
            for f in candidates:
                if f.line is not None:
                    by_file[f.file].append(f)

            clusters: list[list[Finding]] = []
            for file_findings in by_file.values():
                located = sorted(file_findings, key=lambda f: f.line)  # type: ignore[arg-type]
                used: set[str] = set()
                for f in located:
                    if f.id in used:
                        continue
                    group = [
                        g
                        for g in located
                        if g.id not in used and abs(g.line - f.line) <= _LINE_WINDOW
                    ]  # type: ignore[operator]
                    if len({g.detecting_agent for g in group}) >= 2:
                        clusters.append(group)
                        used.update(g.id for g in group)

            corroborating = 0
            conflicting = 0
            conflict_clusters: list[list[str]] = []
            for group in clusters:
                severities = {g.severity for g in group}
                tiers = [_SEVERITY_ORDER[s] for s in severities]
                is_conflict = (max(tiers) - min(tiers)) >= _CONFLICT_SEVERITY_GAP
                agents = sorted({g.detecting_agent for g in group})

                for g in group:
                    others = [a for a in agents if a != g.detecting_agent]
                    if is_conflict:
                        note = (
                            f"Severity conflict at this location: also flagged by {', '.join(others)} with "
                            f"differing severity ({', '.join(sorted(s.value for s in severities))}) - flagged "
                            "for human review."
                        )
                    else:
                        note = (
                            f"Corroborated by {', '.join(others)} at this location - independent signals "
                            "increase confidence this is a real issue."
                        )
                    g.impact = note
                    g.updated_at = now_iso()
                    await ctx.finding_store.update(g)

                if is_conflict:
                    conflicting += 1
                    conflict_clusters.append([g.id for g in group])
                else:
                    corroborating += 1

                await ctx.event_bus.publish(
                    ctx.review_id,
                    EventType.CONFLICT_DETECTED,
                    {
                        "file": group[0].file,
                        "finding_ids": [g.id for g in group],
                        "agents": agents,
                        "severities": sorted(s.value for s in severities),
                        "is_conflict": is_conflict,
                    },
                )

            await self.record_token_usage(
                ctx,
                input_tokens=0,
                output_tokens=0,
                avoided=True,
                reason="Conflict resolution is purely deterministic file/line-window clustering (no LLM judgment)",
            )

            summary = ThinkingSummary(
                objective="Cross-reference findings from different agents that land on overlapping code locations.",
                decision=(
                    f"{len(clusters)} overlapping location(s) found: {corroborating} corroborating, "
                    f"{conflicting} with a severity conflict."
                ),
                action="Clustered CONFIRMED findings by file and a +/-3 line window, grouped by distinct detecting agent.",
                tool="deterministic file/line clustering",
                observation=(
                    f"{conflicting} location(s) have agents disagreeing on severity and were flagged for human review."
                    if conflicting
                    else "No severity conflicts found; any overlaps are corroborating."
                ),
                next_action="Proceed to Final Review.",
            )
            await self.emit_thinking_summary(ctx, summary)

            duration_ms = int((time.perf_counter() - start) * 1000)
            await self.emit_completed(
                ctx, clusters=len(clusters), conflicts=conflicting, duration_ms=duration_ms
            )

            return AgentResult(
                agent_name=self.name,
                status=self.status,
                findings=findings,
                summary=summary,
                tokens_used=0,
                llm_calls_made=0,
                llm_calls_avoided=1,
                duration_ms=duration_ms,
                condition_context={
                    "cluster_count": len(clusters),
                    "conflict_count": conflicting,
                    "conflict_clusters": conflict_clusters,
                },
            )
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - start) * 1000)
            await self.emit_failed(ctx, str(exc))
            return AgentResult(
                agent_name=self.name, status=self.status, error=str(exc), duration_ms=duration_ms
            )
