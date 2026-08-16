from __future__ import annotations

from pathlib import Path

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.base_agent import BaseAgent
from backend.core.agents.llm_json import parse_llm_findings
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.finding import Finding
from backend.core.schemas.tool import ToolResult
from backend.tools.diff.diff_parser_tool import DiffParserTool
from backend.tools.reliability.reliability_heuristic_tool import ReliabilityHeuristicTool
from backend.tools.repository.file_fetch_tool import FileFetchTool


class ReliabilityAgent(BaseAgent):
    """Flags diff-touched functions that call side-effecting methods with no
    surrounding error handling, via real AST analysis; LLM only interprets
    ambiguous cases."""

    name = "reliability_agent"

    def __init__(self) -> None:
        super().__init__()
        self._diff_parser = DiffParserTool()
        self._reliability = ReliabilityHeuristicTool()

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

            reliability_result = await self.call_tool(
                ctx,
                self._reliability,
                {"source": source, "added_lines": diff_result.data.get("added_lines", [])},
            )
            results.append(reliability_result)
            for item in reliability_result.data.get("reliability_findings", []):
                any_signal = True
                await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="reliability_heuristics",
                    agent=self.name,
                    tool="reliability_heuristics",
                    file=pr_file.filename,
                    line=item.get("lineno"),
                    result=item.get("message", ""),
                    confidence=0.6,
                )

        results.append(
            ToolResult(
                success=True,
                tool_name="reliability_signal_summary",
                data={"any_signal": any_signal},
            )
        )
        return results

    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        summary = next(tr for tr in tool_results if tr.tool_name == "reliability_signal_summary")
        if summary.data["any_signal"]:
            return True, ""
        return False, "No unhandled side-effecting-call signals found in the changed files"

    async def interpret(
        self, ctx: AgentContext, tool_results: list[ToolResult], llm_text: str | None
    ) -> tuple[list[Finding], ThinkingSummary]:
        findings, reasoning = parse_llm_findings(
            llm_text, review_id=ctx.review_id, detecting_agent=self.name, category="reliability"
        )
        summary = ThinkingSummary(
            objective="Investigate diff-touched code for unhandled failure modes around side-effecting calls.",
            decision=(
                "Ran AST-based error-handling analysis."
                if llm_text
                else "No reliability signal found; skipped LLM call."
            ),
            action="Analyzed changed Python functions for side-effecting calls with no try/except.",
            tool="reliability_heuristics",
            observation=reasoning
            or "No reliability-relevant evidence produced by deterministic tools.",
            next_action="Send findings to Validator." if findings else "No findings to escalate.",
        )
        return findings, summary
