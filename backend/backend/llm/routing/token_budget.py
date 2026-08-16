from __future__ import annotations

from pydantic import BaseModel

try:
    import tiktoken

    _ENCODING = tiktoken.get_encoding("cl100k_base")
except Exception:  # noqa: BLE001 - pragma: no cover - tiktoken should always be installed, but degrade gracefully
    _ENCODING = None


class TokenBudget(BaseModel):
    max_input_tokens: int = 6000
    max_output_tokens: int = 2000
    timeout_s: float = 30.0


def count_tokens(text: str) -> int:
    """Approximate token count using tiktoken's cl100k_base encoding.

    This is an ESTIMATE for budgeting/UI display purposes only - it does not
    exactly match Groq/Llama tokenization, which has no public offline tokenizer.
    """
    if not text:
        return 0
    if _ENCODING is not None:
        return len(_ENCODING.encode(text))
    return max(1, len(text) // 4)
