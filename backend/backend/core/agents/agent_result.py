from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.core.schemas.agent_state import AgentStatus, ThinkingSummary
from backend.core.schemas.finding import Finding


class AgentResult(BaseModel):
    agent_name: str
    status: AgentStatus
    findings: list[Finding] = Field(default_factory=list)
    summary: ThinkingSummary | None = None
    tokens_used: int = 0
    llm_calls_made: int = 0
    llm_calls_avoided: int = 0
    duration_ms: int = 0
    error: str | None = None
    # Flattened, condition-evaluator-friendly view of this agent's outcome,
    # merged into GraphContext for downstream edge evaluation
    # (e.g. {"findings_count": 2, "max_severity": "HIGH", "tests_failed": True}).
    condition_context: dict[str, Any] = Field(default_factory=dict)
