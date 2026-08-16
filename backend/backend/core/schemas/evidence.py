from __future__ import annotations

from pydantic import BaseModel


class Evidence(BaseModel):
    evidence_id: str
    review_id: str
    source: str  # e.g. "semgrep", "ruff", "ast", "llm:security_agent"
    agent: str
    tool: str | None = None
    file: str | None = None
    line: int | None = None
    result: str
    confidence: float | None = None
    timestamp: str
