from __future__ import annotations

import json

from backend.llm.base.provider import ChatMessage, LLMResponse
from backend.llm.routing.token_budget import count_tokens

_SEVERITY_KEYWORDS = [
    ("CRITICAL", ("remote code execution", "rce", "command injection")),
    (
        "HIGH",
        (
            "sql injection",
            "authorization",
            "auth bypass",
            "hardcoded secret",
            "path traversal",
            "ssrf",
            "xss",
        ),
    ),
    ("MEDIUM", ("missing test", "no test coverage", "null", "race condition", "n+1")),
]

# Ordered (marker, extractor) pairs. The mock provider looks for whichever
# marker is present in the prompt and produces a structurally appropriate,
# fully-grounded (never fabricated) JSON response for that agent's contract.
_EVIDENCE_MARKER = "EVIDENCE_JSON:"
_FINDINGS_MARKER = "FINDINGS_JSON:"
_CONFIRMED_MARKER = "CONFIRMED_FINDINGS_JSON:"
_SUMMARY_MARKER = "SUMMARY_JSON:"
_DEBATE_MARKER = "DEBATE_JSON:"

_SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def _severity_for(text: str) -> str:
    lowered = text.lower()
    for severity, keywords in _SEVERITY_KEYWORDS:
        if any(k in lowered for k in keywords):
            return severity
    return "LOW"


def _extract_json_array(content: str, marker: str) -> list[dict]:
    idx = content.find(marker)
    if idx == -1:
        return []
    tail = content[idx + len(marker) :].strip()
    if not tail.startswith("["):
        return []
    depth = 0
    for i, ch in enumerate(tail):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(tail[: i + 1])
                except json.JSONDecodeError:
                    return []
    return []


def _mock_findings_from_evidence(user_content: str) -> dict:
    evidence_items = _extract_json_array(user_content, _EVIDENCE_MARKER)
    findings = []
    for item in evidence_items:
        result_text = str(item.get("result", ""))
        confidence = item.get("confidence")
        confidence = 0.6 if confidence is None else float(confidence)
        if confidence < 0.3:
            continue
        findings.append(
            {
                "title": result_text[:80],
                "description": result_text,
                "severity": _severity_for(result_text),
                "confidence": round(confidence, 2),
                "file": item.get("file"),
                "line": item.get("line"),
                "evidence_ids": [item.get("evidence_id")] if item.get("evidence_id") else [],
                "recommendation": "Review the flagged evidence and address the underlying issue.",
            }
        )
    return {
        "findings": findings,
        "reasoning": (
            f"[MOCK MODE] Derived directly from {len(evidence_items)} evidence item(s) "
            "already produced by deterministic tools; no LLM call was made."
        ),
    }


def _mock_validator_decisions(user_content: str) -> dict:
    items = _extract_json_array(user_content, _FINDINGS_MARKER)
    decisions = []
    for item in items:
        evidence = item.get("evidence") or []
        confidences = [e.get("confidence") for e in evidence if e.get("confidence") is not None]
        avg_confidence = (
            sum(confidences) / len(confidences) if confidences else item.get("confidence", 0.5)
        )
        status = "CONFIRMED" if avg_confidence >= 0.55 else "REJECTED"
        decisions.append(
            {
                "finding_id": item.get("finding_id"),
                "status": status,
                "confidence": round(float(avg_confidence), 2),
                "rationale": f"[MOCK MODE] Average evidence confidence {avg_confidence:.2f} across {len(evidence)} item(s).",
            }
        )
    return {
        "decisions": decisions,
        "reasoning": f"[MOCK MODE] Validated {len(items)} finding(s) from their existing evidence confidence.",
    }


def _mock_critic_critiques(user_content: str) -> dict:
    items = _extract_json_array(user_content, _CONFIRMED_MARKER)
    critiques = []
    for item in items:
        evidence_ids = item.get("evidence_ids") or []
        confidence = item.get("confidence", 0.5)
        weak = len(evidence_ids) < 1 or confidence < 0.5
        critiques.append(
            {
                "finding_id": item.get("finding_id"),
                "status": "WEAK_EVIDENCE" if weak else "ACCEPTED",
                "notes": (
                    "[MOCK MODE] Fewer than 1 evidence reference or confidence below 0.5."
                    if weak
                    else "[MOCK MODE] Evidence and confidence sufficient."
                ),
            }
        )
    return {
        "critiques": critiques,
        "reasoning": f"[MOCK MODE] Critiqued {len(items)} confirmed finding(s) for evidence sufficiency.",
    }


def _mock_debate_resolution(user_content: str) -> dict:
    """Deterministic stand-in for the arbiter: never invents a comparison,
    only reasons over the positions actually present in the prompt. Same
    `category` across every position -> treated as the same underlying
    issue, resolved to the most severe of the disagreeing assessments (a
    defensible triage default, not a coin flip). Different categories ->
    treated as genuinely independent findings; nothing is changed."""
    items = _extract_json_array(user_content, _DEBATE_MARKER)
    if len(items) < 2:
        return {
            "same_issue": False,
            "resolved_severity": None,
            "rationale": "[MOCK MODE] Fewer than 2 positions to compare.",
            "confidence": 0.0,
        }
    categories = {item.get("category") for item in items}
    same_issue = len(categories) == 1
    if same_issue:
        resolved = max(
            (item.get("severity", "LOW") for item in items), key=lambda s: _SEVERITY_ORDER.get(s, 0)
        )
        rationale = (
            f"[MOCK MODE] All {len(items)} position(s) share category '{items[0].get('category')}' at the same "
            f"location - treated as the same underlying issue, deferring to the more severe assessment ({resolved})."
        )
    else:
        resolved = None
        rationale = (
            f"[MOCK MODE] Positions span different categories ({', '.join(sorted(c for c in categories if c))}) "
            "at the same location - treated as independent findings, not a genuine conflict."
        )
    return {
        "same_issue": same_issue,
        "resolved_severity": resolved,
        "rationale": rationale,
        "confidence": 0.7 if same_issue else 0.9,
    }


def _mock_summary(user_content: str) -> dict:
    idx = user_content.find(_SUMMARY_MARKER)
    titles: list[str] = []
    if idx != -1:
        tail = user_content[idx + len(_SUMMARY_MARKER) :].strip()
        try:
            payload = json.loads(tail)
            titles = [f.get("title", "") for f in payload]
        except json.JSONDecodeError:
            titles = []
    summary = (
        f"This review surfaced {len(titles)} confirmed finding(s): "
        + "; ".join(t for t in titles if t)
        if titles
        else "No confirmed findings requiring attention."
    )
    return {
        "summary": summary,
        "reasoning": "[MOCK MODE] Summary generated by joining confirmed finding titles.",
    }


class MockGroqProvider:
    """Deterministic stand-in for Groq, used when GROQ_API_KEY is unset.

    Never fabricates findings/decisions from nothing: every response is a
    deterministic transform of data already assembled (by tools, or by prior
    deterministic agent logic) into the prompt under one of a few marker
    conventions. Every response is tagged provider_mode='mock' so the UI can
    show a persistent mock-mode banner.
    """

    async def complete(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        max_tokens: int,
        temperature: float = 0.2,
    ) -> LLMResponse:
        user_content = "\n".join(m["content"] for m in messages if m["role"] == "user")

        # _CONFIRMED_MARKER ("CONFIRMED_FINDINGS_JSON:") contains _FINDINGS_MARKER
        # ("FINDINGS_JSON:") as a substring, so it must be checked first.
        if _CONFIRMED_MARKER in user_content:
            payload = _mock_critic_critiques(user_content)
        elif _FINDINGS_MARKER in user_content:
            payload = _mock_validator_decisions(user_content)
        elif _DEBATE_MARKER in user_content:
            payload = _mock_debate_resolution(user_content)
        elif _SUMMARY_MARKER in user_content:
            payload = _mock_summary(user_content)
        else:
            payload = _mock_findings_from_evidence(user_content)

        text = json.dumps(payload)
        return LLMResponse(
            text=text,
            input_tokens=count_tokens(system) + count_tokens(user_content),
            output_tokens=count_tokens(text),
            model="mock-groq",
            provider_mode="mock",
        )
