from __future__ import annotations

import json
import logging

from backend.core.agents.agent_context import AgentContext
from backend.core.orchestration.incremental import classify_findings, compute_delta
from backend.core.orchestration.services import AppServices
from backend.core.schemas.events import EventType
from backend.core.schemas.impact import ImpactAnalysisResult
from backend.core.schemas.review import ReviewSession, ReviewStatus
from backend.core.utils import new_id, now_iso
from backend.integrations.github.schemas import PRFile

logger = logging.getLogger(__name__)


async def run_review(services: AppServices, session: ReviewSession) -> None:
    """Fetches the real PR (diff-first: metadata + files + commits, never the
    whole repo) and runs it through the graph engine. Runs as a background
    task so the webhook/trigger endpoint can return immediately (spec: engine
    kicks off review, returns 202)."""
    review_id = session.review_id
    trace = services.tracing.start_trace(
        review_id, "pr_review", {"repo": session.repo, "pr_number": session.pr_number}
    )
    try:
        pr = await services.github_client.get_pull_request(session.repo, session.pr_number)
        await services.event_bus.publish(
            review_id, EventType.PR_LOADED, {"files_changed": len(pr.files), "title": pr.title}
        )

        session.pr_title = pr.title
        session.head_sha = pr.head_sha
        session.base_sha = pr.base_sha
        session.status = ReviewStatus.ANALYZING
        session.diff_files_json = json.dumps([f.model_dump(mode="json") for f in pr.files])
        session.updated_at = now_iso()
        await services.review_repository.update(session)

        # Incremental PR review (spec: rerun only affected agents on a new
        # push, classify prior findings NEW/RESOLVED/UNCHANGED/STALE/
        # INVALIDATED): when this session chains to a previous one, scope
        # the graph run to just the files that changed since that review -
        # every agent's existing `for pr_file in ctx.diff_files` loop then
        # naturally only re-analyzes the delta, with zero per-agent changes.
        diff_files_for_ctx = pr.files
        previous_session = None
        delta_filenames: set[str] = set()
        if session.previous_review_id:
            previous_session = await services.review_repository.get(session.previous_review_id)
        if previous_session is not None:
            old_files = [PRFile(**f) for f in json.loads(previous_session.diff_files_json or "[]")]
            delta_files = compute_delta(old_files, pr.files)
            diff_files_for_ctx = delta_files
            delta_filenames = {f.filename for f in delta_files}
            await services.event_bus.publish(
                review_id,
                EventType.INCREMENTAL_REVIEW_STARTED,
                {
                    "previous_review_id": previous_session.review_id,
                    "delta_files": sorted(delta_filenames),
                    "delta_count": len(delta_files),
                },
            )

        ctx = AgentContext(
            review_id=review_id,
            pr=pr,
            diff_files=diff_files_for_ctx,
            impact=ImpactAnalysisResult(),
            evidence_store=services.evidence_store,
            finding_store=services.finding_store,
            token_usage_repository=services.token_usage_repository,
            event_bus=services.event_bus,
            message_bus=services.message_bus,
            github_client=services.github_client,
            jira_client=services.jira_client,
            llm=services.llm_provider,
            token_budget=services.token_budget,
            tracing=services.tracing,
            trace=trace,
            tool_cache=services.tool_cache,
            chaos=services.chaos_state,
        )

        await services.graph_engine.run(ctx, session)
        services.tracing.end_trace(trace, status=session.status.value)

        if previous_session is not None:
            await _reconcile_incremental_findings(
                services, review_id, previous_session.review_id, delta_filenames
            )
    except Exception as exc:
        logger.exception("Review %s failed", review_id)
        session.status = ReviewStatus.FAILED
        session.updated_at = now_iso()
        await services.review_repository.update(session)
        await services.event_bus.publish(review_id, EventType.REVIEW_FAILED, {"error": str(exc)})
        services.tracing.end_trace(trace, status="FAILED")


async def _reconcile_incremental_findings(
    services: AppServices, review_id: str, previous_review_id: str, delta_filenames: set[str]
) -> None:
    """Runs after the graph completes (so the delta's own review has
    already been validated/critiqued/published normally): classifies this
    review's fresh findings against the previous review's, persists the
    classification, and carries forward STALE/INVALIDATED findings (as new
    rows chained via `carried_from`) so `GET /{review_id}/findings` shows
    the complete current picture - not just what was re-analyzed this push.
    Scope note: because classification runs after publish, a carried-
    forward finding isn't retroactively added to the GitHub comment this
    push already posted; it's visible from here on (dashboard, findings
    list, Code Explorer, and the next incremental pass's own diff)."""
    old_findings = await services.finding_store.list_by_review(previous_review_id)
    new_findings = await services.finding_store.list_by_review(review_id)
    statuses = classify_findings(old_findings, new_findings, delta_filenames)

    for f in new_findings:
        if f.incremental_status is not None:
            await services.finding_store.update(f)

    for old in old_findings:
        status = statuses.get(old.id)
        if status is None or status.value not in ("STALE", "INVALIDATED"):
            continue
        now = now_iso()
        carried = old.model_copy(
            update={
                "id": new_id("F"),
                "review_id": review_id,
                "incremental_status": status,
                "carried_from": old.id,
                "updated_at": now,
            }
        )
        await services.finding_store.add(carried)

    await services.event_bus.publish(
        review_id,
        EventType.INCREMENTAL_REVIEW_COMPLETED,
        {
            "previous_review_id": previous_review_id,
            "classification": {fid: status.value for fid, status in statuses.items()},
        },
    )
