from __future__ import annotations

from backend.core.events.event_bus import EventBus
from backend.core.schemas.events import EventType
from backend.core.schemas.finding import CriticStatus, Finding, Severity, ValidationStatus
from backend.core.schemas.review import ReviewSession
from backend.integrations.github.client_protocol import GitHubClient
from backend.integrations.github.schemas import InlineComment, ReviewPost

_SEVERITY_ORDER = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}


def _build_finding_body(finding: Finding) -> str:
    lines = [
        f"**{finding.severity.value} — {finding.title}**",
        "",
        finding.description,
    ]
    if finding.impact:
        lines += ["", f"**Impact:** {finding.impact}"]
    if finding.evidence_ids:
        lines += ["", f"**Evidence:** {', '.join(finding.evidence_ids)}"]
    lines += ["", f"**Validated by:** Validator Agent ({finding.validator_status.value})"]
    lines += [f"**Confidence:** {finding.confidence:.0%}"]
    if finding.recommendation:
        lines += ["", f"**Recommendation:** {finding.recommendation}"]
    return "\n".join(lines)


def build_review_post(session: ReviewSession, findings: list[Finding]) -> ReviewPost:
    publishable = [
        f
        for f in findings
        if f.validator_status == ValidationStatus.CONFIRMED
        and f.critic_status in (CriticStatus.ACCEPTED,)
    ]
    comments = [
        InlineComment(path=f.file, line=f.line, body=_build_finding_body(f))
        for f in publishable
        if f.line
    ]

    high_or_above = [
        f for f in publishable if _SEVERITY_ORDER[f.severity] >= _SEVERITY_ORDER[Severity.HIGH]
    ]
    event = "REQUEST_CHANGES" if high_or_above else "COMMENT"

    summary_lines = [
        f"## Multi-Agent PR Review — PR #{session.pr_number}",
        "",
        f"{len(publishable)} confirmed finding(s), {len(high_or_above)} at HIGH severity or above.",
    ]
    return ReviewPost(body="\n".join(summary_lines), event=event, comments=comments)


async def publish_review(
    session: ReviewSession,
    findings: list[Finding],
    github_client: GitHubClient,
    event_bus: EventBus,
) -> dict:
    review_post = build_review_post(session, findings)
    result = await github_client.post_review(session.repo, session.pr_number, review_post)
    await event_bus.publish(
        session.review_id,
        EventType.GITHUB_UPDATED,
        {"review_post": review_post.model_dump(), "result": result},
    )
    return result
