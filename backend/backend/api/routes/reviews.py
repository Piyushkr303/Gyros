from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.api.deps import get_services
from backend.core.orchestration.human_approval import ApprovalAction, ApprovalDecision
from backend.core.orchestration.review_runner import run_review
from backend.core.orchestration.services import AppServices
from backend.core.schemas.review import ReviewSession, ReviewStatus
from backend.core.utils import new_id, now_iso

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("")
async def list_reviews(services: AppServices = Depends(get_services)) -> list[dict]:
    reviews = await services.review_repository.list_all()
    return [r.model_dump(mode="json") for r in reviews]


@router.get("/{review_id}")
async def get_review(review_id: str, services: AppServices = Depends(get_services)) -> dict:
    review = await services.review_repository.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review.model_dump(mode="json")


@router.get("/{review_id}/findings")
async def get_findings(review_id: str, services: AppServices = Depends(get_services)) -> list[dict]:
    findings = await services.finding_store.list_by_review(review_id)
    return [f.model_dump(mode="json") for f in findings]


@router.get("/{review_id}/evidence")
async def get_evidence(review_id: str, services: AppServices = Depends(get_services)) -> list[dict]:
    items = services.evidence_store.query(review_id)
    return [e.model_dump(mode="json") for e in items]


@router.get("/{review_id}/tokens")
async def get_token_usage(
    review_id: str, services: AppServices = Depends(get_services)
) -> list[dict]:
    records = await services.token_usage_repository.list_by_review(review_id)
    return [r.model_dump(mode="json") for r in records]


@router.get("/{review_id}/graph")
async def get_graph_topology(review_id: str, services: AppServices = Depends(get_services)) -> dict:
    definition = services.graph_definition
    return {
        "nodes": [n.model_dump() for n in definition.nodes],
        "edges": [e.model_dump() for e in definition.to_conditional_edges()],
    }


@router.get("/{review_id}/events")
async def get_review_events(
    review_id: str, services: AppServices = Depends(get_services)
) -> list[dict]:
    """Full persisted event history for a review - the same backlog a WS
    client gets on connect, exposed as plain REST so a past (possibly
    long-finished) review can be replayed without opening a live socket."""
    events = await services.event_bus.history(review_id)
    return [e.model_dump(mode="json") for e in events]


@router.get("/{review_id}/files")
async def get_review_files(
    review_id: str, services: AppServices = Depends(get_services)
) -> list[dict]:
    """Changed-file list for Code Explorer, re-fetched on demand from the
    GitHub client (real or mock) rather than persisted separately."""
    review = await services.review_repository.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    files = await services.github_client.get_pr_files(review.repo, review.pr_number)
    return [f.model_dump(mode="json") for f in files]


@router.get("/{review_id}/files/content")
async def get_review_file_content(
    review_id: str, path: str, services: AppServices = Depends(get_services)
) -> dict:
    review = await services.review_repository.get(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    content = await services.github_client.get_file_content(review.repo, path, review.head_sha)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found at this ref")
    return {"path": path, "ref": review.head_sha, "content": content}


class ApprovalRequest(BaseModel):
    edited_body: str | None = None


@router.post("/{review_id}/approve")
async def approve_review(review_id: str, services: AppServices = Depends(get_services)) -> dict:
    resolved = services.human_approval_gate.resolve(
        review_id, ApprovalDecision(action=ApprovalAction.APPROVE)
    )
    if not resolved:
        raise HTTPException(status_code=409, detail="No pending approval for this review")
    return {"review_id": review_id, "action": "APPROVE"}


@router.post("/{review_id}/reject")
async def reject_review(review_id: str, services: AppServices = Depends(get_services)) -> dict:
    resolved = services.human_approval_gate.resolve(
        review_id, ApprovalDecision(action=ApprovalAction.REJECT)
    )
    if not resolved:
        raise HTTPException(status_code=409, detail="No pending approval for this review")
    return {"review_id": review_id, "action": "REJECT"}


@router.post("/{review_id}/edit")
async def edit_review(
    review_id: str, request: ApprovalRequest, services: AppServices = Depends(get_services)
) -> dict:
    resolved = services.human_approval_gate.resolve(
        review_id, ApprovalDecision(action=ApprovalAction.EDIT, edited_body=request.edited_body)
    )
    if not resolved:
        raise HTTPException(status_code=409, detail="No pending approval for this review")
    return {"review_id": review_id, "action": "EDIT"}


@router.post("/trigger-demo", status_code=202)
async def trigger_demo_review(
    request: Request, services: AppServices = Depends(get_services)
) -> dict:
    """Bypasses the real GitHub webhook and runs a review directly against the
    local demo PR fixture (tests/fixtures/demo_pr) - the fastest way to see
    the full graph execute without needing a real PR or webhook secret."""
    meta = json.loads((services.settings.fixtures_dir / "pr_meta.json").read_text(encoding="utf-8"))

    review_id = new_id("rev")
    session = ReviewSession(
        review_id=review_id,
        pr_number=meta["number"],
        repo=meta["repo"],
        pr_title=meta["title"],
        head_sha=meta["head_sha"],
        base_sha=meta["base_sha"],
        status=ReviewStatus.RECEIVED,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    await services.review_repository.add(session)

    task = asyncio.create_task(run_review(services, session))
    request.app.state.background_tasks.add(task)
    task.add_done_callback(request.app.state.background_tasks.discard)

    return {"review_id": review_id, "status": "accepted"}


@router.post("/trigger-demo-followup", status_code=202)
async def trigger_demo_followup_review(
    request: Request, services: AppServices = Depends(get_services)
) -> dict:
    """Simulates a second push to the same demo PR (spec: incremental
    review) - advances MockGitHubClient's fixture to its follow-up revision
    (mock mode only) and chains a new ReviewSession to the most recent
    review for the same PR via previous_review_id, so run_review() takes
    the delta-only incremental path instead of re-analyzing from scratch."""
    github_client = services.github_client
    if (
        not hasattr(github_client, "has_followup_revision")
        or not github_client.has_followup_revision()
    ):
        raise HTTPException(
            status_code=409, detail="No follow-up fixture revision available (demo mock mode only)"
        )

    meta = json.loads((services.settings.fixtures_dir / "pr_meta.json").read_text(encoding="utf-8"))
    previous = await services.review_repository.find_latest_by_pr(meta["repo"], meta["number"])
    if previous is None:
        raise HTTPException(
            status_code=409,
            detail="No prior review found for this PR - trigger the initial demo first",
        )

    github_client.advance_revision()

    review_id = new_id("rev")
    session = ReviewSession(
        review_id=review_id,
        pr_number=meta["number"],
        repo=meta["repo"],
        status=ReviewStatus.RECEIVED,
        previous_review_id=previous.review_id,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    await services.review_repository.add(session)

    task = asyncio.create_task(run_review(services, session))
    request.app.state.background_tasks.add(task)
    task.add_done_callback(request.app.state.background_tasks.discard)

    return {"review_id": review_id, "status": "accepted", "previous_review_id": previous.review_id}
