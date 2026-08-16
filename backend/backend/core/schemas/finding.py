from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ValidationStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    UNCERTAIN = "UNCERTAIN"


class CriticStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    WEAK_EVIDENCE = "WEAK_EVIDENCE"
    DUPLICATE = "DUPLICATE"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class IncrementalStatus(StrEnum):
    """Set only on findings that went through incremental re-review
    classification (core/orchestration/incremental.py); None on a finding
    from a first-time (non-incremental) review."""

    NEW = "NEW"
    RESOLVED = "RESOLVED"
    UNCHANGED = "UNCHANGED"
    STALE = "STALE"
    INVALIDATED = "INVALIDATED"


class Finding(BaseModel):
    id: str
    review_id: str
    severity: Severity
    category: str
    file: str
    line: int | None = None
    title: str
    description: str
    evidence_ids: list[str] = Field(default_factory=list)
    impact: str = ""
    recommendation: str = ""
    confidence: float = 0.0
    detecting_agent: str
    validator_status: ValidationStatus = ValidationStatus.PENDING
    validator_confidence: float | None = None
    critic_status: CriticStatus = CriticStatus.PENDING
    critic_notes: str | None = None
    reanalysis_count: int = 0
    incremental_status: IncrementalStatus | None = None
    carried_from: str | None = None
    # Set only when this finding was part of a genuine severity conflict
    # that Debate Agent arbitrated (core/agents/debate) - None otherwise.
    debate_resolution: str | None = None
    created_at: str
    updated_at: str
