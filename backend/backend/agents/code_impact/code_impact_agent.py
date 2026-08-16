from __future__ import annotations

from pathlib import Path

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.base_agent import BaseAgent
from backend.core.agents.llm_json import parse_llm_findings
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.finding import Finding
from backend.core.schemas.tool import ToolResult
from backend.tools.ast_tool.python_ast_tool import PythonAstTool
from backend.tools.code_impact.code_impact_heuristic_tool import CodeImpactHeuristicTool
from backend.tools.diff.diff_parser_tool import DiffParserTool
from backend.tools.repository.file_fetch_tool import FileFetchTool


class CodeImpactAgent(BaseAgent):
    """Builds a real function-level call graph (networkx) among this PR's
    diff-touched functions to measure blast radius within the diff itself -
    which touched functions are relied on by other touched functions. LLM
    only interprets ambiguous cases."""

    name = "code_impact_agent"

    def __init__(self) -> None:
        super().__init__()
        self._diff_parser = DiffParserTool()
        self._python_ast = PythonAstTool()
        self._code_impact = CodeImpactHeuristicTool()

    async def run_deterministic_tools(self, ctx: AgentContext) -> list[ToolResult]:
        results: list[ToolResult] = []
        file_tool = FileFetchTool(ctx.github_client)
        functions: list[dict] = []

        for pr_file in ctx.diff_files:
            if Path(pr_file.filename).suffix.lstrip(".") != "py":
                continue

            diff_result = await self.call_tool(
                ctx, self._diff_parser, {"filename": pr_file.filename, "patch": pr_file.patch}
            )
            results.append(diff_result)

            fetched = await self.call_tool(
                ctx,
                file_tool,
                {"repo": ctx.pr.repo, "path": pr_file.filename, "ref": ctx.pr.head_sha},
            )
            results.append(fetched)
            source = fetched.data.get("content") or ""
            if not source:
                continue

            ast_result = await self.call_tool(
                ctx,
                self._python_ast,
                {
                    "filename": pr_file.filename,
                    "source": source,
                    "added_lines": diff_result.data.get("added_lines", []),
                },
            )
            results.append(ast_result)
            for fn in ast_result.data.get("touched_functions", []):
                functions.append(
                    {
                        "name": fn["name"],
                        "file": pr_file.filename,
                        "lineno": fn["lineno"],
                        "calls": fn.get("calls", []),
                    }
                )

        impact_result = await self.call_tool(ctx, self._code_impact, {"functions": functions})
        results.append(impact_result)

        any_signal = bool(impact_result.data.get("code_impact_findings"))
        for item in impact_result.data.get("code_impact_findings", []):
            await ctx.evidence_store.add(
                review_id=ctx.review_id,
                source="code_impact_heuristics",
                agent=self.name,
                tool="code_impact_heuristics",
                file=item.get("file"),
                line=item.get("lineno"),
                result=item.get("message", ""),
                confidence=0.55,
            )

        results.append(
            ToolResult(
                success=True,
                tool_name="code_impact_signal_summary",
                data={"any_signal": any_signal},
            )
        )
        return results

    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        summary = next(tr for tr in tool_results if tr.tool_name == "code_impact_signal_summary")
        if summary.data["any_signal"]:
            return True, ""
        return False, "No diff-touched function is called by multiple other diff-touched functions"

    async def interpret(
        self, ctx: AgentContext, tool_results: list[ToolResult], llm_text: str | None
    ) -> tuple[list[Finding], ThinkingSummary]:
        findings, reasoning = parse_llm_findings(
            llm_text, review_id=ctx.review_id, detecting_agent=self.name, category="code_impact"
        )
        summary = ThinkingSummary(
            objective="Measure the blast radius of this PR's diff-touched functions within the diff itself.",
            decision=(
                "Built a function-level call graph (networkx) among diff-touched functions."
                if llm_text
                else "No high-fan-in touched function found; skipped LLM call."
            ),
            action="Correlated each touched function's calls against the set of other touched functions.",
            tool="code_impact_heuristics",
            observation=reasoning
            or "No code-impact-relevant evidence produced by deterministic tools.",
            next_action="Send findings to Validator." if findings else "No findings to escalate.",
        )
        return findings, summary
