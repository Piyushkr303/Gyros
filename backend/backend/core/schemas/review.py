from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ReviewStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PLANNING = "PLANNING"
    ANALYZING = "ANALYZING"
    VALIDATING = "VALIDATING"
    CRITIQUING = "CRITIQUING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class ReviewSession(BaseModel):
    review_id: str
    pr_number: int
    repo: str
    pr_title: str = ""
    head_sha: str = ""
    base_sha: str = ""
    status: ReviewStatus = ReviewStatus.RECEIVED
    # Incremental PR review (spec: rerun on a synchronize push, classify
    # prior findings) - see core/orchestration/incremental.py.
    previous_review_id: str | None = None
    # This review's own PRFile list, serialized, so a LATER review that
    # chains to this one via previous_review_id can diff against exactly
    # what was analyzed here without needing to re-fetch/re-derive it.
    diff_files_json: str = "[]"
    created_at: str
    updated_at: str
