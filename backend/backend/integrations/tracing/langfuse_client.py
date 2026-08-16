from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from langfuse import Langfuse

    _LANGFUSE_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when the optional SDK isn't installed
    _LANGFUSE_AVAILABLE = False


def is_langfuse_available() -> bool:
    return _LANGFUSE_AVAILABLE


class LangfuseTracingClient:
    """Real Langfuse tracing - one Langfuse trace per review, one span per
    agent run. Only constructed when LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY
    are set AND the `langfuse` SDK is importable (see factory.py); falls
    back to NoOpTracingClient otherwise, the same graceful-degradation shape
    the ruff/semgrep/pylint subprocess tools use for a missing binary,
    applied to a missing/unconfigured SDK instead."""

    def __init__(self, public_key: str, secret_key: str, host: str) -> None:
        self._client = Langfuse(public_key=public_key, secret_key=secret_key, host=host or None)

    def start_trace(self, review_id: str, name: str, metadata: dict[str, Any]) -> Any:
        return self._client.trace(name=name, id=review_id, metadata=metadata)

    def log_agent_span(
        self,
        trace: Any,
        *,
        agent_name: str,
        input_summary: dict[str, Any],
        output_summary: dict[str, Any],
        llm_call_made: bool,
        duration_ms: int,
    ) -> None:
        if trace is None:
            return
        trace.span(
            name=agent_name,
            input=input_summary,
            output=output_summary,
            metadata={"llm_call_made": llm_call_made, "duration_ms": duration_ms},
        )

    def end_trace(self, trace: Any, *, status: str) -> None:
        if trace is None:
            return
        trace.update(output={"status": status})
        self._client.flush()
