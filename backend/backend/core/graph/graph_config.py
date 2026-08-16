from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from backend.core.schemas.edge import ConditionalEdge, ConditionType


class GraphNodeConfig(BaseModel):
    id: str
    label: str
    kind: str = "agent"  # agent | orchestration


class GraphEdgeConfig(BaseModel):
    source: str
    target: str
    condition: str = "True"
    type: ConditionType = ConditionType.ALWAYS
    priority: int = 0
    enabled: bool = True


class GraphDefinition(BaseModel):
    nodes: list[GraphNodeConfig] = Field(default_factory=list)
    edges: list[GraphEdgeConfig] = Field(default_factory=list)

    def to_conditional_edges(self) -> list[ConditionalEdge]:
        edges: list[ConditionalEdge] = []
        for i, e in enumerate(self.edges):
            edges.append(
                ConditionalEdge(
                    edge_id=f"edge-{e.source}-{e.target}-{i}",
                    source_agent=e.source,
                    target_agent=e.target,
                    condition=e.condition,
                    condition_type=e.type,
                    priority=e.priority,
                    enabled=e.enabled,
                )
            )
        return edges

    def edges_from(self, source: str) -> list[ConditionalEdge]:
        return [e for e in self.to_conditional_edges() if e.source_agent == source]


def load_graph_definition(path: Path) -> GraphDefinition:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return GraphDefinition.model_validate(raw)
