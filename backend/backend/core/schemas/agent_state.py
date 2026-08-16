from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class AgentStatus(StrEnum):
    IDLE = "IDLE"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    THINKING_SUMMARY = "THINKING_SUMMARY"
    CALLING_TOOL = "CALLING_TOOL"
    WAITING = "WAITING"
    COMMUNICATING = "COMMUNICATING"
    VALIDATING = "VALIDATING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"


class ThinkingSummary(BaseModel):
    """Safe, structured execution summary. Never raw chain-of-thought (spec §67)."""

    objective: str
    decision: str
    action: str
    tool: str | None = None
    observation: str
    next_action: str
