from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from backend.core.schemas.edge import ConditionType
from backend.core.schemas.events import Event, EventType
from backend.core.schemas.evidence import Evidence
from backend.core.schemas.finding import (
    CriticStatus,
    Finding,
    IncrementalStatus,
    Severity,
    ValidationStatus,
)
from backend.core.schemas.message import AgentMessage, MessageType
from backend.core.schemas.review import ReviewSession, ReviewStatus
from backend.core.schemas.token_usage import TokenUsageRecord


class ReviewSessionRow(SQLModel, table=True):
    __tablename__ = "review_sessions"

    review_id: str = Field(primary_key=True)
    pr_number: int
    repo: str
    pr_title: str = ""
    head_sha: str = ""
    base_sha: str = ""
    status: str = ReviewStatus.RECEIVED.value
    previous_review_id: str | None = None
    diff_files_json: str = "[]"
    created_at: str
    updated_at: str

    def to_domain(self) -> ReviewSession:
        return ReviewSession(
            review_id=self.review_id,
            pr_number=self.pr_number,
            repo=self.repo,
            pr_title=self.pr_title,
            head_sha=self.head_sha,
            base_sha=self.base_sha,
            status=ReviewStatus(self.status),
            previous_review_id=self.previous_review_id,
            diff_files_json=self.diff_files_json,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_domain(cls, obj: ReviewSession) -> ReviewSessionRow:
        return cls(
            review_id=obj.review_id,
            pr_number=obj.pr_number,
            repo=obj.repo,
            pr_title=obj.pr_title,
            head_sha=obj.head_sha,
            base_sha=obj.base_sha,
            status=obj.status.value,
            previous_review_id=obj.previous_review_id,
            diff_files_json=obj.diff_files_json,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class FindingRow(SQLModel, table=True):
    __tablename__ = "findings"

    id: str = Field(primary_key=True)
    review_id: str = Field(index=True)
    severity: str
    category: str
    file: str
    line: int | None = None
    title: str
    description: str
    evidence_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    impact: str = ""
    recommendation: str = ""
    confidence: float = 0.0
    detecting_agent: str
    validator_status: str = ValidationStatus.PENDING.value
    validator_confidence: float | None = None
    critic_status: str = CriticStatus.PENDING.value
    critic_notes: str | None = None
    reanalysis_count: int = 0
    incremental_status: str | None = None
    carried_from: str | None = None
    debate_resolution: str | None = None
    created_at: str
    updated_at: str

    def to_domain(self) -> Finding:
        return Finding(
            id=self.id,
            review_id=self.review_id,
            severity=Severity(self.severity),
            category=self.category,
            file=self.file,
            line=self.line,
            title=self.title,
            description=self.description,
            evidence_ids=self.evidence_ids,
            impact=self.impact,
            recommendation=self.recommendation,
            confidence=self.confidence,
            detecting_agent=self.detecting_agent,
            validator_status=ValidationStatus(self.validator_status),
            validator_confidence=self.validator_confidence,
            critic_status=CriticStatus(self.critic_status),
            critic_notes=self.critic_notes,
            reanalysis_count=self.reanalysis_count,
            incremental_status=IncrementalStatus(self.incremental_status)
            if self.incremental_status
            else None,
            carried_from=self.carried_from,
            debate_resolution=self.debate_resolution,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_domain(cls, obj: Finding) -> FindingRow:
        return cls(
            id=obj.id,
            review_id=obj.review_id,
            severity=obj.severity.value,
            category=obj.category,
            file=obj.file,
            line=obj.line,
            title=obj.title,
            description=obj.description,
            evidence_ids=list(obj.evidence_ids),
            impact=obj.impact,
            recommendation=obj.recommendation,
            confidence=obj.confidence,
            detecting_agent=obj.detecting_agent,
            validator_status=obj.validator_status.value,
            validator_confidence=obj.validator_confidence,
            critic_status=obj.critic_status.value,
            critic_notes=obj.critic_notes,
            reanalysis_count=obj.reanalysis_count,
            incremental_status=obj.incremental_status.value if obj.incremental_status else None,
            carried_from=obj.carried_from,
            debate_resolution=obj.debate_resolution,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class EvidenceRow(SQLModel, table=True):
    __tablename__ = "evidence"

    evidence_id: str = Field(primary_key=True)
    review_id: str = Field(index=True)
    source: str
    agent: str
    tool: str | None = None
    file: str | None = None
    line: int | None = None
    result: str
    confidence: float | None = None
    timestamp: str

    def to_domain(self) -> Evidence:
        return Evidence(**self.model_dump())

    @classmethod
    def from_domain(cls, obj: Evidence) -> EvidenceRow:
        return cls(**obj.model_dump())


class EventRow(SQLModel, table=True):
    __tablename__ = "events"

    id: str = Field(primary_key=True)
    review_id: str = Field(index=True)
    type: str
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    def to_domain(self) -> Event:
        return Event(
            id=self.id,
            type=EventType(self.type),
            review_id=self.review_id,
            timestamp=self.timestamp,
            payload=self.payload,
        )

    @classmethod
    def from_domain(cls, obj: Event) -> EventRow:
        return cls(
            id=obj.id,
            review_id=obj.review_id,
            type=obj.type.value,
            timestamp=obj.timestamp,
            payload=obj.payload,
        )


class TokenUsageRow(SQLModel, table=True):
    __tablename__ = "token_usage"

    id: str = Field(primary_key=True)
    review_id: str = Field(index=True)
    agent: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str | None = None
    llm_call_avoided: bool = False
    avoided_reason: str | None = None
    provider_mode: str = "mock"
    timestamp: str

    def to_domain(self) -> TokenUsageRecord:
        return TokenUsageRecord(**self.model_dump())

    @classmethod
    def from_domain(cls, obj: TokenUsageRecord) -> TokenUsageRow:
        return cls(**obj.model_dump())


class AgentMessageRow(SQLModel, table=True):
    __tablename__ = "agent_messages"

    message_id: str = Field(primary_key=True)
    review_id: str = Field(index=True)
    sender: str
    receiver: str
    type: str
    finding_id: str | None = None
    summary: str
    evidence_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    confidence: float | None = None
    timestamp: str

    def to_domain(self) -> AgentMessage:
        return AgentMessage(
            message_id=self.message_id,
            review_id=self.review_id,
            sender=self.sender,
            receiver=self.receiver,
            type=MessageType(self.type),
            finding_id=self.finding_id,
            summary=self.summary,
            evidence_ids=self.evidence_ids,
            confidence=self.confidence,
            timestamp=self.timestamp,
        )

    @classmethod
    def from_domain(cls, obj: AgentMessage) -> AgentMessageRow:
        return cls(
            message_id=obj.message_id,
            review_id=obj.review_id,
            sender=obj.sender,
            receiver=obj.receiver,
            type=obj.type.value,
            finding_id=obj.finding_id,
            summary=obj.summary,
            evidence_ids=list(obj.evidence_ids),
            confidence=obj.confidence,
            timestamp=obj.timestamp,
        )


class ToolResultCacheRow(SQLModel, table=True):
    __tablename__ = "tool_result_cache"

    cache_key: str = Field(primary_key=True)
    tool_name: str = Field(index=True)
    success: bool
    data_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    error: str | None = None
    hit_count: int = 0
    created_at: str


# ConditionType import kept for downstream repository type hints / re-export convenience.
__all__ = [
    "AgentMessageRow",
    "ConditionType",
    "EventRow",
    "EvidenceRow",
    "FindingRow",
    "ReviewSessionRow",
    "TokenUsageRow",
    "ToolResultCacheRow",
]
