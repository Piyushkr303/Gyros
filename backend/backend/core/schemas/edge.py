from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class ConditionType(StrEnum):
    ALWAYS = "ALWAYS"
    IF = "IF"
    ELSE = "ELSE"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    THRESHOLD = "THRESHOLD"
    EVENT = "EVENT"
    AGENT_RESULT = "AGENT_RESULT"
    TOOL_RESULT = "TOOL_RESULT"


class ConditionalEdge(BaseModel):
    edge_id: str
    source_agent: str
    target_agent: str
    condition: str
    condition_type: ConditionType
    priority: int = 0
    enabled: bool = True


class EdgeEvaluationResult(BaseModel):
    edge_id: str
    review_id: str
    passed: bool
    value: Any = None
    reason: str
    evaluated_at: str
