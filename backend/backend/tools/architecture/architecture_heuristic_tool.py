from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx

from backend.tools.base import Tool

_HIGH_FAN_IN = 3


def _module_stem(filename: str) -> str:
    return Path(filename).stem


class ArchitectureHeuristicTool(Tool):
    """Builds a real import-dependency graph (networkx) across this PR's
    changed Python files and detects circular imports and highly-coupled
    (high fan-in) modules within the diff. Scoped to the diff, not a
    whole-repo crawl - it only knows about files actually present in this PR."""

    name = "architecture_heuristics"
    description = (
        "Detect circular imports and high-coupling modules among changed Python files via networkx."
    )

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        files: list[dict] = input.get("files") or []
        stems = {_module_stem(f["filename"]): f["filename"] for f in files}

        graph: nx.DiGraph = nx.DiGraph()
        for f in files:
            graph.add_node(f["filename"])
        for f in files:
            for imp in f.get("imports", []):
                imp_stem = imp.split(".")[0]
                target = stems.get(imp_stem)
                if target and target != f["filename"]:
                    graph.add_edge(f["filename"], target)

        findings: list[dict] = []
        for cycle in nx.simple_cycles(graph):
            if len(cycle) < 2:
                continue
            path = " -> ".join([*cycle, cycle[0]])
            findings.append(
                {
                    "type": "circular_import",
                    "message": f"Circular import among changed files: {path}.",
                }
            )

        for node in graph.nodes:
            fan_in = graph.in_degree(node)
            if fan_in >= _HIGH_FAN_IN:
                findings.append(
                    {
                        "type": "high_coupling",
                        "message": (
                            f"'{node}' is imported by {fan_in} other changed files in this diff - a "
                            "high-coupling hub worth double-checking for behavior changes."
                        ),
                    }
                )

        return {"architecture_findings": findings}
