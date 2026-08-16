from __future__ import annotations

import json
import time

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.agent_result import AgentResult
from backend.core.agents.agent_support import AgentSupport
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.events import EventType
from backend.core.schemas.finding import Finding, ValidationStatus
from backend.core.utils import now_iso
from backend.llm.base.provider import ChatMessage
from backend.tools.diff.diff_parser_tool import DiffParserTool

_CONFIDENCE_CONFIRM = 0.75
_CONFIDENCE_REJECT = 0.35


class ValidatorAgent(AgentSupport):
    """Verifies findings are actually true (spec §32): does the evidence
    exist, and does file:line actually fall within the diff? Deterministic
    checks resolve most findings; the LLM is only consulted for the
    remaining ambiguous (UNCERTAIN) cases."""

    name = "validator_agent"

    def __init__(self) -> None:
        super().__init__()
        self._diff_parser = DiffParserTool()

    async def _added_lines_by_file(self, ctx: AgentContext) -> dict[str, set[int]]:
        result: dict[str, set[int]] = {}
        for pr_file in ctx.diff_files:
            diff_result = await self._diff_parser.execute(
                {"filename": pr_file.filename, "patch": pr_file.patch}
            )
            result[pr_file.filename] = set(diff_result.data.get("added_lines", []))
        return result

    async def run(self, ctx: AgentContext, findings: list[Finding]) -> AgentResult:
        start = time.perf_counter()
        await self.emit_started(ctx)

        try:
            added_lines_by_file = await self._added_lines_by_file(ctx)
            uncertain: list[Finding] = []
            confirmed_count = 0
            rejected_count = 0

            for finding in findings:
                evidence_ok = (
                    all(ctx.evidence_store.get(eid) is not None for eid in finding.evidence_ids)
                    if finding.evidence_ids
                    else True
                )
                line_ok = True
                if finding.line is not None:
                    added = added_lines_by_file.get(finding.file)
                    if added is not None:
                        line_ok = finding.line in added

                if not evidence_ok or not line_ok:
                    finding.validator_status = ValidationStatus.REJECTED
                    finding.validator_confidence = 0.0
                    rejected_count += 1
                    await self._finalize(ctx, finding, EventType.FINDING_REJECTED)
                elif finding.confidence >= _CONFIDENCE_CONFIRM:
                    finding.validator_status = ValidationStatus.CONFIRMED
                    finding.validator_confidence = finding.confidence
                    confirmed_count += 1
                    await self._finalize(ctx, finding, EventType.FINDING_VALIDATED)
                elif finding.confidence < _CONFIDENCE_REJECT:
                    finding.validator_status = ValidationStatus.REJECTED
                    finding.validator_confidence = finding.confidence
                    rejected_count += 1
                    await self._finalize(ctx, finding, EventType.FINDING_REJECTED)
                else:
                    finding.validator_status = ValidationStatus.UNCERTAIN
                    uncertain.append(finding)

            llm_calls_made = 0
            llm_calls_avoided = 0
            tokens_used = 0

            if uncertain:
                llm_calls_made = 1
                user_content = self._build_prompt(ctx, uncertain)
                messages: list[ChatMessage] = [{"role": "user", "content": user_content}]
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
                decisions = self._parse_decisions(response.text)
                for finding in uncertain:
                    decision = decisions.get(finding.id)
                    if decision is None:
                        await ctx.finding_store.update(finding)
                        continue
                    status = str(decision.get("status", "UNCERTAIN")).upper()
                    finding.validator_confidence = float(
                        decision.get("confidence", finding.confidence)
                    )
                    if status == "CONFIRMED":
                        finding.validator_status = ValidationStatus.CONFIRMED
                        confirmed_count += 1
                        await self._finalize(ctx, finding, EventType.FINDING_VALIDATED)
                    elif status == "REJECTED":
                        finding.validator_status = ValidationStatus.REJECTED
                        rejected_count += 1
                        await self._finalize(ctx, finding, EventType.FINDING_REJECTED)
                    else:
                        await ctx.finding_store.update(finding)
            else:
                llm_calls_avoided = 1
                await self.record_token_usage(
                    ctx,
                    input_tokens=0,
                    output_tokens=0,
                    avoided=True,
                    reason="All findings resolved by deterministic evidence/confidence checks",
                )

            still_uncertain = [
                f for f in findings if f.validator_status == ValidationStatus.UNCERTAIN
            ]

            summary = ThinkingSummary(
                objective="Verify that each finding is backed by real evidence and matches the actual diff.",
                decision=(
                    f"{confirmed_count} confirmed, {rejected_count} rejected, "
                    f"{len(still_uncertain)} still uncertain."
                ),
                action="Checked evidence existence and file:line alignment with the diff for every finding.",
                tool="evidence_store + diff_parser" + (" + LLM" if uncertain else ""),
                observation=f"{len(uncertain)} finding(s) needed LLM judgment after deterministic checks.",
                next_action=(
                    "Send confirmed findings to Critic."
                    if confirmed_count
                    else "No confirmed findings to escalate."
                ),
            )
            await self.emit_thinking_summary(ctx, summary)

            duration_ms = int((time.perf_counter() - start) * 1000)
            await self.emit_completed(
                ctx, confirmed=confirmed_count, rejected=rejected_count, duration_ms=duration_ms
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
                    "confirmed_count": confirmed_count,
                    "rejected_count": rejected_count,
                    "uncertain_count": len(still_uncertain),
                },
            )
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - start) * 1000)
            await self.emit_failed(ctx, str(exc))
            return AgentResult(
                agent_name=self.name, status=self.status, error=str(exc), duration_ms=duration_ms
            )

    async def _finalize(self, ctx: AgentContext, finding: Finding, event_type: EventType) -> None:
        finding.updated_at = now_iso()
        await ctx.finding_store.update(finding)
        await ctx.event_bus.publish(
            ctx.review_id, event_type, {"finding": finding.model_dump(mode="json")}
        )

    def _system_prompt(self) -> str:
        return (
            "You are the Validator Agent. Respond ONLY with strict JSON: "
            '{"decisions": [{"finding_id": str, "status": "CONFIRMED"|"REJECTED", '
            '"confidence": float, "rationale": str}], "reasoning": str}. '
            "Base each decision only on the evidence provided for that finding."
        )

    def _build_prompt(self, ctx: AgentContext, uncertain: list[Finding]) -> str:
        items = []
        for f in uncertain:
            evidence = [
                {"result": e.result, "confidence": e.confidence, "source": e.source}
                for eid in f.evidence_ids
                if (e := ctx.evidence_store.get(eid)) is not None
            ]
            items.append(
                {
                    "finding_id": f.id,
                    "title": f.title,
                    "description": f.description,
                    "confidence": f.confidence,
                    "evidence": evidence,
                }
            )
        return f"Findings requiring validation judgment:\n\nFINDINGS_JSON:\n{json.dumps(items)}"

    def _parse_decisions(self, llm_text: str) -> dict[str, dict]:
        try:
            payload = json.loads(llm_text)
        except json.JSONDecodeError:
            return {}
        return {d.get("finding_id"): d for d in payload.get("decisions", []) if d.get("finding_id")}
