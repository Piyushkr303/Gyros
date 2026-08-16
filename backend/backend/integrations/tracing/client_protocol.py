from __future__ import annotations

from typing import Any, Protocol


class TracingClient(Protocol):
    """Spec: Langfuse/LangSmith tracing. One trace covers a single review;
    each agent run within it is logged as one span, so LLM calls (and the
    deterministic tool calls that fed them) are inspectable in the external
    tracing UI - the same information this project's own Traces page shows,
    exported for teams already standardized on Langfuse/LangSmith."""

    def start_trace(self, review_id: str, name: str, metadata: dict[str, Any]) -> Any: ...

    def log_agent_span(
        self,
        trace: Any,
        *,
        agent_name: str,
        input_summary: dict[str, Any],
        output_summary: dict[str, Any],
        llm_call_made: bool,
        duration_ms: int,
    ) -> None: ...

    def end_trace(self, trace: Any, *, status: str) -> None: ...
