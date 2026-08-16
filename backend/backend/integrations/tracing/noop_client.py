from __future__ import annotations

from typing import Any


class NoOpTracingClient:
    """Default tracing backend when no Langfuse/LangSmith credentials (or
    SDKs) are configured - a genuine no-op, not a fake success, so
    BaseAgent/GraphEngine can call the TracingClient interface
    unconditionally regardless of what's configured (same shape as
    MockGroqProvider/MockGitHubClient never fabricating data, just simpler:
    there's nothing to mock, tracing is purely additive observability)."""

    def start_trace(self, review_id: str, name: str, metadata: dict[str, Any]) -> Any:
        return None

    def log_agent_span(self, trace: Any, **kwargs: Any) -> None:
        return None

    def end_trace(self, trace: Any, *, status: str) -> None:
        return None
