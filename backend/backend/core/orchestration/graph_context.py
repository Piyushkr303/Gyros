from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.core.agents.agent_result import AgentResult
from backend.core.schemas.impact import ImpactAnalysisResult


@dataclass
class GraphContext:
    """Accumulated, condition-evaluator-friendly state for one review's graph run."""

    review_id: str
    impact: ImpactAnalysisResult | None = None
    agent_results: dict[str, AgentResult] = field(default_factory=dict)
    reanalysis_counts: dict[str, int] = field(default_factory=dict)
    last_event: dict[str, Any] = field(default_factory=dict)

    def record_agent_result(self, agent_name: str, result: AgentResult) -> None:
        self.agent_results[agent_name] = result

    def as_condition_dict(self) -> dict[str, Any]:
        flat: dict[str, Any] = {}
        if self.impact is not None:
            flat.update(self.impact.model_dump())
        for agent_name, result in self.agent_results.items():
            agent_view = {
                "status": result.status.value,
                "findings_count": len(result.findings),
                "llm_calls_made": result.llm_calls_made,
                "llm_calls_avoided": result.llm_calls_avoided,
                **result.condition_context,
            }
            flat[agent_name] = agent_view
            # Also expose as flat `<agent>_<key>` for simple single-name conditions.
            for key, value in agent_view.items():
                flat[f"{agent_name}_{key}"] = value
        flat["last_event"] = self.last_event
        return flat
