from __future__ import annotations

from pathlib import Path

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.base_agent import BaseAgent
from backend.core.agents.llm_json import parse_llm_findings
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.finding import Finding
from backend.core.schemas.tool import ToolResult
from backend.tools.ast_tool.python_ast_tool import PythonAstTool
from backend.tools.diff.diff_parser_tool import DiffParserTool
from backend.tools.repository.file_fetch_tool import FileFetchTool


class DocumentationAgent(BaseAgent):
    """Checks whether diff-touched public functions have a docstring. AST-only
    signal (reuses PythonAstTool's has_docstring flag); LLM only judges
    whether a flagged function's purpose is non-obvious enough to warrant one."""

    name = "documentation_agent"

    def __init__(self) -> None:
        super().__init__()
        self._diff_parser = DiffParserTool()
        self._python_ast = PythonAstTool()

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
                if fn["name"].startswith("_") or fn["has_docstring"]:
                    continue
                any_signal = True
                await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="ast",
                    agent=self.name,
                    tool="python_ast",
                    file=pr_file.filename,
                    line=fn["lineno"],
                    result=f"Public function '{fn['name']}' was added/modified in this diff but has no docstring.",
                    confidence=0.5,
                )

        results.append(
            ToolResult(
                success=True,
                tool_name="documentation_signal_summary",
                data={"any_signal": any_signal},
            )
        )
        return results

    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        summary = next(tr for tr in tool_results if tr.tool_name == "documentation_signal_summary")
        if summary.data["any_signal"]:
            return True, ""
        return False, "Every diff-touched public function already has a docstring"

    async def interpret(
        self, ctx: AgentContext, tool_results: list[ToolResult], llm_text: str | None
    ) -> tuple[list[Finding], ThinkingSummary]:
        findings, reasoning = parse_llm_findings(
            llm_text, review_id=ctx.review_id, detecting_agent=self.name, category="documentation"
        )
        summary = ThinkingSummary(
            objective="Check that diff-touched public functions are documented.",
            decision=(
                "Ran AST docstring analysis on changed Python files."
                if llm_text
                else "All touched public functions already documented; skipped LLM call."
            ),
            action="Compared touched_functions against has_docstring.",
            tool="python_ast",
            observation=reasoning
            or "No missing-docstring evidence produced by deterministic tools.",
            next_action="Send findings to Validator." if findings else "No findings to escalate.",
        )
        return findings, summary
