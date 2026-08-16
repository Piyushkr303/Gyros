from __future__ import annotations

import json
import logging

from backend.core.schemas.finding import Finding, Severity
from backend.core.utils import new_id, now_iso

logger = logging.getLogger(__name__)


def parse_llm_findings(
    llm_text: str | None,
    *,
    review_id: str,
    detecting_agent: str,
    category: str,
) -> tuple[list[Finding], str]:
    """Parse the shared {"findings": [...], "reasoning": str} JSON contract
    every LLM-calling agent's system prompt requests. Returns (findings, reasoning).
    Malformed/missing JSON degrades to an empty finding list rather than raising,
    since a bad LLM response must not crash the graph."""
    if not llm_text:
        return [], ""

    try:
        payload = json.loads(llm_text)
    except json.JSONDecodeError:
        logger.warning("Agent %s: LLM response was not valid JSON", detecting_agent)
        return [], ""

    reasoning = str(payload.get("reasoning", ""))
    findings: list[Finding] = []
    for item in payload.get("findings", []):
        try:
            severity = Severity(str(item.get("severity", "LOW")).upper())
        except ValueError:
            severity = Severity.LOW
        confidence = item.get("confidence")
        try:
            confidence = float(confidence) if confidence is not None else 0.5
        except (TypeError, ValueError):
            confidence = 0.5

        timestamp = now_iso()
        findings.append(
            Finding(
                id=new_id("F"),
                review_id=review_id,
                severity=severity,
                category=category,
                file=str(item.get("file") or "unknown"),
                line=item.get("line"),
                title=str(item.get("title") or item.get("description", ""))[:120]
                or "Untitled finding",
                description=str(item.get("description", "")),
                evidence_ids=list(item.get("evidence_ids") or []),
                impact=str(item.get("impact", "")),
                recommendation=str(item.get("recommendation", "")),
                confidence=confidence,
                detecting_agent=detecting_agent,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
    return findings, reasoning
