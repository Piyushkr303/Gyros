from __future__ import annotations

from pathlib import Path

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.base_agent import BaseAgent
from backend.core.agents.llm_json import parse_llm_findings
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.finding import Finding
from backend.core.schemas.tool import ToolResult
from backend.tools.lint.pylint_tool import PylintTool
from backend.tools.repository.file_fetch_tool import FileFetchTool

_SEVERITY_MAP = {"error": "HIGH", "warning": "MEDIUM", "refactor": "LOW"}


class StaticAnalysisAgent(BaseAgent):
    """Runs pylint (real subprocess, graceful not-installed fallback) against
    changed Python files - a distinct rule surface (design smells like
    too-many-branches, broad-except) from Bug Detection's ruff pass and
    Security's semgrep pass. LLM only interprets ambiguous cases."""

    name = "static_analysis_agent"

    def __init__(self) -> None:
        super().__init__()
        self._pylint = PylintTool()

    async def run_deterministic_tools(self, ctx: AgentContext) -> list[ToolResult]:
        results: list[ToolResult] = []
        any_signal = False

        for pr_file in ctx.diff_files:
            if Path(pr_file.filename).suffix.lstrip(".") != "py":
                continue

            file_tool = FileFetchTool(ctx.github_client)
            fetched = await self.call_tool(
                ctx,
                file_tool,
                {"repo": ctx.pr.repo, "path": pr_file.filename, "ref": ctx.pr.head_sha},
            )
            results.append(fetched)
            source = fetched.data.get("content") or ""

            pylint_result = await self.call_tool(
                ctx, self._pylint, {"filename": pr_file.filename, "source": source}
            )
            results.append(pylint_result)
            for violation in pylint_result.data.get("violations", []):
                any_signal = True
                severity_hint = _SEVERITY_MAP.get(violation.get("type", ""), "LOW")
                await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="pylint",
                    agent=self.name,
                    tool="pylint",
                    file=pr_file.filename,
                    line=violation.get("lineno"),
                    result=f"[{violation.get('symbol')}] {violation.get('message')} (suggested severity: {severity_hint})",
                    confidence=0.65,
                )

        results.append(
            ToolResult(
                success=True,
                tool_name="static_analysis_signal_summary",
                data={"any_signal": any_signal},
            )
        )
        return results

    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        summary = next(
            tr for tr in tool_results if tr.tool_name == "static_analysis_signal_summary"
        )
        if summary.data["any_signal"]:
            return True, ""
        return False, "No pylint violations found in the changed files (or pylint is not installed)"

    async def interpret(
        self, ctx: AgentContext, tool_results: list[ToolResult], llm_text: str | None
    ) -> tuple[list[Finding], ThinkingSummary]:
        findings, reasoning = parse_llm_findings(
            llm_text, review_id=ctx.review_id, detecting_agent=self.name, category="static_analysis"
        )
        summary = ThinkingSummary(
            objective="Run static analysis (pylint) over changed Python files for design/convention issues.",
            decision="Ran pylint." if llm_text else "No pylint signal found; skipped LLM call.",
            action="Analyzed changed Python files with pylint (docstring rules disabled - covered by Documentation Agent).",
            tool="pylint",
            observation=reasoning
            or "No static-analysis-relevant evidence produced by deterministic tools.",
            next_action="Send findings to Validator." if findings else "No findings to escalate.",
        )
        return findings, summary
