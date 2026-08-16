from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class TokenUsageRecord(BaseModel):
    id: str
    review_id: str
    agent: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str | None = None
    llm_call_avoided: bool = False
    avoided_reason: str | None = None
    provider_mode: Literal["real", "mock"] = "mock"
    timestamp: str
