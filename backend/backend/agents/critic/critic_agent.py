from __future__ import annotations

import json
import time

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.agent_result import AgentResult
from backend.core.agents.agent_support import AgentSupport
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.events import EventType
from backend.core.schemas.finding import CriticStatus, Finding, ValidationStatus
from backend.core.utils import now_iso
from backend.llm.base.provider import ChatMessage

_MIN_EVIDENCE_FOR_AUTO_ACCEPT = 2
_MIN_CONFIDENCE_FOR_AUTO_ACCEPT = 0.7


class CriticAgent(AgentSupport):
    """Asks a different question than the Validator (spec §33): not "is this
    true" but "is this useful, correctly classified, sufficiently evidenced,
    non-duplicate, and appropriately prioritized". Deduplication and
    high-confidence auto-accept are deterministic; the LLM only judges
    borderline evidence-sufficiency cases."""

    name = "critic_agent"

    async def run(self, ctx: AgentContext, findings: list[Finding]) -> AgentResult:
        start = time.perf_counter()
        await self.emit_started(ctx)

        try:
            confirmed = [f for f in findings if f.validator_status == ValidationStatus.CONFIRMED]

            seen: dict[tuple, Finding] = {}
            duplicate_of: dict[str, Finding] = {}
            duplicates: list[Finding] = []
            unique: list[Finding] = []
            for f in confirmed:
                # file+line+category identifies "same code location" for
                # line-anchored findings. PR-level findings with no line
                # (e.g. Requirement Agent's acceptance-criteria checks) fall
                # back to file+category+title so distinct findings that only
                # share "no specific line" don't get falsely collapsed.
                key = (
                    (f.file, f.line, f.category)
                    if f.line is not None
                    else (f.file, f.category, f.title)
                )
                if key in seen:
                    duplicate_of[f.id] = seen[key]
                    duplicates.append(f)
                else:
                    seen[key] = f
                    unique.append(f)

            for f in duplicates:
                f.critic_status = CriticStatus.DUPLICATE
                f.critic_notes = f"Duplicate of finding at the same file:line:category as {duplicate_of[f.id].id}"
                await self._finalize(ctx, f)

            ambiguous: list[Finding] = []
            accepted_count = 0
            for f in unique:
                if (
                    len(f.evidence_ids) >= _MIN_EVIDENCE_FOR_AUTO_ACCEPT
                    and f.confidence >= _MIN_CONFIDENCE_FOR_AUTO_ACCEPT
                ):
                    f.critic_status = CriticStatus.ACCEPTED
                    f.critic_notes = "Auto-accepted: sufficient evidence count and confidence."
                    accepted_count += 1
                    await self._finalize(ctx, f)
                else:
                    ambiguous.append(f)

            llm_calls_made = 0
            llm_calls_avoided = 0
            tokens_used = 0
            weak_evidence_count = 0

            if ambiguous:
                llm_calls_made = 1
                messages: list[ChatMessage] = [
                    {"role": "user", "content": self._build_prompt(ambiguous)}
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
                critiques = self._parse_critiques(response.text)
                for f in ambiguous:
                    critique = critiques.get(f.id)
                    status = str((critique or {}).get("status", "WEAK_EVIDENCE")).upper()
                    f.critic_notes = (critique or {}).get("notes", "No rationale provided.")
                    if status == "ACCEPTED":
                        f.critic_status = CriticStatus.ACCEPTED
                        accepted_count += 1
                    else:
                        f.critic_status = CriticStatus.WEAK_EVIDENCE
                        weak_evidence_count += 1
                    await self._finalize(ctx, f)
            else:
                llm_calls_avoided = 1
                await self.record_token_usage(
                    ctx,
                    input_tokens=0,
                    output_tokens=0,
                    avoided=True,
                    reason="All confirmed findings resolved by deterministic dedup/evidence-count rules",
                )

            summary = ThinkingSummary(
                objective="Assess whether confirmed findings are non-duplicate, well-evidenced, and worth reporting.",
                decision=(
                    f"{accepted_count} accepted, {weak_evidence_count} flagged weak-evidence, "
                    f"{len(duplicates)} duplicates removed."
                ),
                action="Deduplicated by file:line:category, then evaluated evidence sufficiency.",
                tool="dedup_heuristic" + (" + LLM" if ambiguous else ""),
                observation=f"{len(ambiguous)} finding(s) needed LLM judgment on evidence sufficiency.",
                next_action=(
                    "Send weak-evidence findings back to Validator for re-investigation."
                    if weak_evidence_count
                    else "Proceed to Final Review."
                ),
            )
            await self.emit_thinking_summary(ctx, summary)

            duration_ms = int((time.perf_counter() - start) * 1000)
            await self.emit_completed(
                ctx,
                accepted=accepted_count,
                weak_evidence=weak_evidence_count,
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
                condition_context={
                    "accepted_count": accepted_count,
                    "weak_evidence_count": weak_evidence_count,
                    "duplicate_count": len(duplicates),
                },
            )
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - start) * 1000)
            await self.emit_failed(ctx, str(exc))
            return AgentResult(
                agent_name=self.name, status=self.status, error=str(exc), duration_ms=duration_ms
            )

    async def _finalize(self, ctx: AgentContext, finding: Finding) -> None:
        finding.updated_at = now_iso()
        await ctx.finding_store.update(finding)
        await ctx.event_bus.publish(
            ctx.review_id,
            EventType.FINDING_CRITICIZED,
            {"finding": finding.model_dump(mode="json")},
        )

    def _system_prompt(self) -> str:
        return (
            "You are the Critic Agent. Respond ONLY with strict JSON: "
            '{"critiques": [{"finding_id": str, "status": "ACCEPTED"|"WEAK_EVIDENCE", '
            '"notes": str}], "reasoning": str}. '
            "A finding is WEAK_EVIDENCE if its evidence would not convince a skeptical senior engineer."
        )

    def _build_prompt(self, ambiguous: list[Finding]) -> str:
        items = [
            {
                "finding_id": f.id,
                "title": f.title,
                "confidence": f.confidence,
                "evidence_ids": f.evidence_ids,
            }
            for f in ambiguous
        ]
        return f"Confirmed findings requiring critique:\n\nCONFIRMED_FINDINGS_JSON:\n{json.dumps(items)}"

    def _parse_critiques(self, llm_text: str) -> dict[str, dict]:
        try:
            payload = json.loads(llm_text)
        except json.JSONDecodeError:
            return {}
        return {c.get("finding_id"): c for c in payload.get("critiques", []) if c.get("finding_id")}
