from __future__ import annotations

from typing import Any

from backend.integrations.tracing.client_protocol import TracingClient


class CompositeTracingClient:
    """Fans one review's trace out to every configured tracing backend at
    once - e.g. Langfuse and LangSmith simultaneously, since they're not
    mutually exclusive external observability sinks - so GraphEngine/
    BaseAgent only ever talk to a single TracingClient regardless of how
    many (zero, one, or both) are actually configured."""

    def __init__(self, clients: list[TracingClient]) -> None:
        self._clients = clients

    def start_trace(self, review_id: str, name: str, metadata: dict[str, Any]) -> list[Any]:
        return [c.start_trace(review_id, name, metadata) for c in self._clients]

    def log_agent_span(self, traces: list[Any], **kwargs: Any) -> None:
        for client, trace in zip(self._clients, traces, strict=True):
            client.log_agent_span(trace, **kwargs)

    def end_trace(self, traces: list[Any], *, status: str) -> None:
        for client, trace in zip(self._clients, traces, strict=True):
            client.end_trace(trace, status=status)
