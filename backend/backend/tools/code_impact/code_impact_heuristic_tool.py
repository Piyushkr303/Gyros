from __future__ import annotations

from typing import Any

import networkx as nx

from backend.tools.base import Tool

_HIGH_FAN_IN = 2


class CodeImpactHeuristicTool(Tool):
    """Builds a real function-level call graph (networkx) among this PR's
    diff-touched functions and flags touched functions called by multiple
    OTHER diff-touched functions - a concrete, diff-scoped measure of blast
    radius (not a whole-repo guess, and not tree-sitter/multi-language - this
    project's real analysis is Python-only via the stdlib `ast` module)."""

    name = "code_impact_heuristics"
    description = (
        "Build a call graph among diff-touched functions and flag high-fan-in touched functions."
    )

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        functions: list[dict] = input.get("functions") or []
        touched_names = {f["name"] for f in functions}

        graph: nx.DiGraph = nx.DiGraph()
        for f in functions:
            graph.add_node(f["name"])
        for f in functions:
            for callee in f.get("calls", []):
                if callee in touched_names and callee != f["name"]:
                    graph.add_edge(f["name"], callee)

        by_name = {f["name"]: f for f in functions}
        findings: list[dict] = []
        for node in graph.nodes:
            fan_in = graph.in_degree(node)
            if fan_in >= _HIGH_FAN_IN:
                callers = sorted({u for u, _ in graph.in_edges(node)})
                info = by_name[node]
                findings.append(
                    {
                        "file": info["file"],
                        "lineno": info["lineno"],
                        "type": "high_fan_in",
                        "message": (
                            f"'{node}' is called by {fan_in} other diff-touched function(s) "
                            f"({', '.join(callers)}); verify its behavior change is compatible with every "
                            "caller in this PR."
                        ),
                    }
                )

        return {"code_impact_findings": findings}
