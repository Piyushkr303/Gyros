from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

try:
    from langsmith import Client

    _LANGSMITH_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when the optional SDK isn't installed
    _LANGSMITH_AVAILABLE = False


def is_langsmith_available() -> bool:
    return _LANGSMITH_AVAILABLE


class LangSmithTracingClient:
    """Real LangSmith tracing via the `langsmith` SDK's Client.create_run/
    update_run - one root run per review, one child run per agent. Same
    import-guarded availability pattern as LangfuseTracingClient; the two
    are not mutually exclusive (see CompositeTracingClient)."""

    def __init__(self, api_key: str, project: str) -> None:
        self._client = Client(api_key=api_key)
        self._project = project

    def start_trace(self, review_id: str, name: str, metadata: dict[str, Any]) -> Any:
        run_id = uuid.uuid4()
        self._client.create_run(
            name=name,
            run_type="chain",
            id=run_id,
            inputs=metadata,
            project_name=self._project,
        )
        return run_id

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
        child_id = uuid.uuid4()
        self._client.create_run(
            name=agent_name,
            run_type="chain",
            id=child_id,
            parent_run_id=trace,
            inputs=input_summary,
            project_name=self._project,
        )
        self._client.update_run(
            child_id,
            outputs={**output_summary, "llm_call_made": llm_call_made, "duration_ms": duration_ms},
        )

    def end_trace(self, trace: Any, *, status: str) -> None:
        if trace is None:
            return
        self._client.update_run(trace, outputs={"status": status})
