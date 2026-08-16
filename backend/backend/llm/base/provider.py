from __future__ import annotations

from typing import Literal, Protocol, TypedDict

from pydantic import BaseModel


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMResponse(BaseModel):
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    provider_mode: Literal["real", "mock"]


class LLMProvider(Protocol):
    async def complete(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        max_tokens: int,
        temperature: float = 0.2,
    ) -> LLMResponse: ...
