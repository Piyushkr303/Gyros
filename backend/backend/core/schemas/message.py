from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class MessageType(StrEnum):
    FINDING = "FINDING"
    VALIDATION = "VALIDATION"
    CRITIQUE = "CRITIQUE"
    REQUEST_EVIDENCE = "REQUEST_EVIDENCE"
    INFO = "INFO"


class AgentMessage(BaseModel):
    message_id: str
    review_id: str
    sender: str
    receiver: str
    type: MessageType
    finding_id: str | None = None
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float | None = None
    timestamp: str
