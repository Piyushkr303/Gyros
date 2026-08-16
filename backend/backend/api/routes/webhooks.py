from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from backend.api.deps import get_services
from backend.core.orchestration.review_runner import run_review
from backend.core.orchestration.services import AppServices
from backend.core.schemas.events import EventType
from backend.core.schemas.review import ReviewSession, ReviewStatus
from backend.core.utils import new_id, now_iso
from backend.integrations.github.webhook_security import verify_signature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_HANDLED_ACTIONS = {"opened", "reopened", "synchronize"}


@router.post("/github", status_code=202)
async def github_webhook(
    request: Request,
    services: AppServices = Depends(get_services),
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
) -> dict:
    body = await request.body()

    if not verify_signature(body, x_hub_signature_256, services.settings.github_webhook_secret):
        logger.warning("Webhook rejected: invalid signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    if x_github_event != "pull_request":
        return {"ignored": True, "reason": f"unsupported event type {x_github_event}"}

    payload = json.loads(body)
    action = payload.get("action")
    if action not in _HANDLED_ACTIONS:
        return {"ignored": True, "reason": f"unsupported action {action}"}

    pr_json = payload["pull_request"]
    repo = payload["repository"]["full_name"]
    pr_number = pr_json["number"]
    review_id = new_id("rev")

    # Incremental PR review: a `synchronize` action IS "this PR got pushed
    # to again" - if a prior review for the same repo+PR already exists,
    # chain this one to it so run_review() takes the delta-only path
    # instead of re-analyzing the whole PR from scratch.
    previous_review_id = None
    if action == "synchronize":
        previous = await services.review_repository.find_latest_by_pr(repo, pr_number)
        previous_review_id = previous.review_id if previous else None

    session = ReviewSession(
        review_id=review_id,
        pr_number=pr_number,
        repo=repo,
        pr_title=pr_json.get("title", ""),
        head_sha=pr_json["head"]["sha"],
        base_sha=pr_json["base"]["sha"],
        status=ReviewStatus.RECEIVED,
        previous_review_id=previous_review_id,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    await services.review_repository.add(session)
    await services.event_bus.publish(
        review_id,
        EventType.WEBHOOK_RECEIVED,
        {"action": action, "repo": repo, "pr_number": session.pr_number},
    )

    task = asyncio.create_task(run_review(services, session))
    request.app.state.background_tasks.add(task)
    task.add_done_callback(request.app.state.background_tasks.discard)

    return {"review_id": review_id, "status": "accepted"}
