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
from backend.tools.lint.ruff_tool import RuffTool
from backend.tools.repository.file_fetch_tool import FileFetchTool

_HIGH_ARG_COUNT = 6


class BugDetectionAgent(BaseAgent):
    """Analyzes logic bugs, null handling, boundary conditions, and regression
    risk. Ruff + AST run first; the LLM only interprets ambiguous cases (spec §16)."""

    name = "bug_detection_agent"

    def __init__(self) -> None:
        super().__init__()
        self._diff_parser = DiffParserTool()
        self._python_ast = PythonAstTool()
        self._ruff = RuffTool()

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

            ruff_result = await self.call_tool(
                ctx, self._ruff, {"filename": pr_file.filename, "source": source}
            )
            results.append(ruff_result)
            for violation in ruff_result.data.get("violations", []):
                any_signal = True
                await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="ruff",
                    agent=self.name,
                    tool="ruff",
                    file=pr_file.filename,
                    line=violation.get("lineno"),
                    result=f"[{violation.get('code')}] {violation.get('message')}",
                    confidence=0.75,
                )

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
                if fn["arg_count"] >= _HIGH_ARG_COUNT:
                    any_signal = True
                    await ctx.evidence_store.add(
                        review_id=ctx.review_id,
                        source="ast",
                        agent=self.name,
                        tool="python_ast",
                        file=pr_file.filename,
                        line=fn["lineno"],
                        result=(
                            f"Function '{fn['name']}' takes {fn['arg_count']} parameters, "
                            "which increases risk of incorrect call-site assumptions."
                        ),
                        confidence=0.55,
                    )

        results.append(
            ToolResult(
                success=True, tool_name="bug_signal_summary", data={"any_signal": any_signal}
            )
        )
        return results

    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        summary = next(tr for tr in tool_results if tr.tool_name == "bug_signal_summary")
        if summary.data["any_signal"]:
            return True, ""
        return False, "No ruff violations or AST complexity signals found"

    async def interpret(
        self, ctx: AgentContext, tool_results: list[ToolResult], llm_text: str | None
    ) -> tuple[list[Finding], ThinkingSummary]:
        findings, reasoning = parse_llm_findings(
            llm_text, review_id=ctx.review_id, detecting_agent=self.name, category="bug"
        )
        summary = ThinkingSummary(
            objective="Investigate the diff for logic bugs, boundary conditions, and regression risk.",
            decision="Ran ruff and AST complexity analysis."
            if llm_text
            else "No bug signal found; skipped LLM call.",
            action="Analyzed changed Python files for lint violations and touched-function complexity.",
            tool="ruff + python_ast",
            observation=reasoning or "No bug-relevant evidence produced by deterministic tools.",
            next_action="Send findings to Validator." if findings else "No findings to escalate.",
        )
        return findings, summary
