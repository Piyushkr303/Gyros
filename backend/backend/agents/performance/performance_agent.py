from __future__ import annotations

from pathlib import Path

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.base_agent import BaseAgent
from backend.core.agents.llm_json import parse_llm_findings
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.finding import Finding
from backend.core.schemas.tool import ToolResult
from backend.tools.diff.diff_parser_tool import DiffParserTool
from backend.tools.performance.performance_heuristic_tool import PerformanceHeuristicTool
from backend.tools.repository.file_fetch_tool import FileFetchTool


class PerformanceAgent(BaseAgent):
    """Flags nested-loop and in-loop-accumulation patterns in diff-touched
    Python code via real AST analysis; LLM only interprets ambiguous cases."""

    name = "performance_agent"

    def __init__(self) -> None:
        super().__init__()
        self._diff_parser = DiffParserTool()
        self._performance = PerformanceHeuristicTool()

    async def run_deterministic_tools(self, ctx: AgentContext) -> list[ToolResult]:
        results: list[ToolResult] = []
        any_signal = False

        for pr_file in ctx.diff_files:
            if Path(pr_file.filename).suffix.lstrip(".") != "py":
                continue

            diff_result = await self.call_tool(
                ctx, self._diff_parser, {"filename": pr_file.filename, "patch": pr_file.patch}
            )
            results.append(diff_result)

            file_tool = FileFetchTool(ctx.github_client)
            fetched = await self.call_tool(
                ctx,
                file_tool,
                {"repo": ctx.pr.repo, "path": pr_file.filename, "ref": ctx.pr.head_sha},
            )
            results.append(fetched)
            source = fetched.data.get("content") or ""

            perf_result = await self.call_tool(
                ctx,
                self._performance,
                {"source": source, "added_lines": diff_result.data.get("added_lines", [])},
            )
            results.append(perf_result)
            for item in perf_result.data.get("performance_findings", []):
                any_signal = True
                await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="performance_heuristics",
                    agent=self.name,
                    tool="performance_heuristics",
                    file=pr_file.filename,
                    line=item.get("lineno"),
                    result=item.get("message", ""),
                    confidence=0.55,
                )

        results.append(
            ToolResult(
                success=True,
                tool_name="performance_signal_summary",
                data={"any_signal": any_signal},
            )
        )
        return results

    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        summary = next(tr for tr in tool_results if tr.tool_name == "performance_signal_summary")
        if summary.data["any_signal"]:
            return True, ""
        return False, "No nested-loop or in-loop-accumulation signals found in the changed files"

    async def interpret(
        self, ctx: AgentContext, tool_results: list[ToolResult], llm_text: str | None
    ) -> tuple[list[Finding], ThinkingSummary]:
        findings, reasoning = parse_llm_findings(
            llm_text, review_id=ctx.review_id, detecting_agent=self.name, category="performance"
        )
        summary = ThinkingSummary(
            objective="Investigate diff-touched code for O(n^2)+ risk patterns.",
            decision=(
                "Ran AST-based nested-loop and accumulation analysis."
                if llm_text
                else "No performance signal found; skipped LLM call."
            ),
            action="Analyzed changed Python files for nested loops and in-loop accumulation.",
            tool="performance_heuristics",
            observation=reasoning
            or "No performance-relevant evidence produced by deterministic tools.",
            next_action="Send findings to Validator." if findings else "No findings to escalate.",
        )
        return findings, summary
