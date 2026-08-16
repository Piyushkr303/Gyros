from __future__ import annotations

from backend.core.events.event_bus import EventBus
from backend.core.schemas.events import EventType
from backend.core.schemas.finding import CriticStatus, Finding, ValidationStatus
from backend.core.schemas.review import ReviewSession
from backend.integrations.jira.client_protocol import JiraClient

_STATUS_ON_APPROVE = "In Review"
_STATUS_ON_REJECT = "Needs Work"


def _build_comment(session: ReviewSession, findings: list[Finding], approved: bool) -> str:
    publishable = [
        f
        for f in findings
        if f.validator_status == ValidationStatus.CONFIRMED
        and f.critic_status == CriticStatus.ACCEPTED
    ]
    outcome = "approved and published to GitHub" if approved else "rejected"
    lines = [
        f"Multi-Agent PR Review {outcome} for PR #{session.pr_number} ({session.repo}).",
        f"{len(publishable)} confirmed finding(s) at review time.",
    ]
    return "\n".join(lines)


async def publish_jira_update(
    session: ReviewSession,
    findings: list[Finding],
    issue_key: str,
    approved: bool,
    jira_client: JiraClient,
    event_bus: EventBus,
) -> None:
    """Posts the review outcome back to the linked Jira ticket (comment +
    status transition) - symmetric with github_publisher.publish_review, but
    only runs when Requirement Agent actually found a ticket reference in
    the PR title/body (see GraphEngine.run: issue_key comes from
    requirement_agent's condition_context, not re-parsed here)."""
    comment_posted = await jira_client.add_comment(
        issue_key, _build_comment(session, findings, approved)
    )
    status = _STATUS_ON_APPROVE if approved else _STATUS_ON_REJECT
    transitioned = await jira_client.transition_status(issue_key, status)
    await event_bus.publish(
        session.review_id,
        EventType.JIRA_UPDATED,
        {
            "issue_key": issue_key,
            "comment_posted": comment_posted,
            "transitioned_to": status if transitioned else None,
        },
    )
