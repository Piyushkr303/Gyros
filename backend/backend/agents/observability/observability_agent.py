from __future__ import annotations

from pathlib import Path

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.base_agent import BaseAgent
from backend.core.agents.llm_json import parse_llm_findings
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.finding import Finding
from backend.core.schemas.tool import ToolResult
from backend.tools.diff.diff_parser_tool import DiffParserTool
from backend.tools.observability.observability_heuristic_tool import ObservabilityHeuristicTool
from backend.tools.repository.file_fetch_tool import FileFetchTool


class ObservabilityAgent(BaseAgent):
    """Flags diff-touched critical-action functions with no audit-trail
    logging, and except blocks that silently swallow failures, via real AST
    analysis. Distinct from Reliability Agent: that agent checks for missing
    error *handling* (no try/except); this one checks for missing error
    *visibility* (no logging) even where handling exists."""

    name = "observability_agent"

    def __init__(self) -> None:
        super().__init__()
        self._diff_parser = DiffParserTool()
        self._observability = ObservabilityHeuristicTool()

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

            obs_result = await self.call_tool(
                ctx,
                self._observability,
                {"source": source, "added_lines": diff_result.data.get("added_lines", [])},
            )
            results.append(obs_result)
            for item in obs_result.data.get("observability_findings", []):
                any_signal = True
                await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="observability_heuristics",
                    agent=self.name,
                    tool="observability_heuristics",
                    file=pr_file.filename,
                    line=item.get("lineno"),
                    result=item.get("message", ""),
                    confidence=0.55,
                )

        results.append(
            ToolResult(
                success=True,
                tool_name="observability_signal_summary",
                data={"any_signal": any_signal},
            )
        )
        return results

    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        summary = next(tr for tr in tool_results if tr.tool_name == "observability_signal_summary")
        if summary.data["any_signal"]:
            return True, ""
        return False, "No missing-audit-logging or silently-swallowed-exception signals found"

    async def interpret(
        self, ctx: AgentContext, tool_results: list[ToolResult], llm_text: str | None
    ) -> tuple[list[Finding], ThinkingSummary]:
        findings, reasoning = parse_llm_findings(
            llm_text, review_id=ctx.review_id, detecting_agent=self.name, category="observability"
        )
        summary = ThinkingSummary(
            objective="Check that diff-touched critical actions and failure paths are observable in production.",
            decision=(
                "Ran AST-based audit-logging and exception-visibility analysis."
                if llm_text
                else "No observability gaps found; skipped LLM call."
            ),
            action="Analyzed changed Python functions for missing logging and silently-swallowed exceptions.",
            tool="observability_heuristics",
            observation=reasoning
            or "No observability-relevant evidence produced by deterministic tools.",
            next_action="Send findings to Validator." if findings else "No findings to escalate.",
        )
        return findings, summary
