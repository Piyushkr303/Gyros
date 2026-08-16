from __future__ import annotations

from pydantic import BaseModel, Field


class JiraIssue(BaseModel):
    key: str
    summary: str = ""
    status: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
