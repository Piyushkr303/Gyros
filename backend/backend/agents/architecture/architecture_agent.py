from __future__ import annotations

from pathlib import Path

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.base_agent import BaseAgent
from backend.core.agents.llm_json import parse_llm_findings
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.finding import Finding
from backend.core.schemas.tool import ToolResult
from backend.tools.architecture.architecture_heuristic_tool import ArchitectureHeuristicTool
from backend.tools.ast_tool.python_ast_tool import PythonAstTool
from backend.tools.repository.file_fetch_tool import FileFetchTool


class ArchitectureAgent(BaseAgent):
    """Builds a real import-dependency graph (networkx) across this PR's
    changed Python files to detect circular imports and high-fan-in coupling
    hubs within the diff. LLM only interprets ambiguous cases."""

    name = "architecture_agent"

    def __init__(self) -> None:
        super().__init__()
        self._python_ast = PythonAstTool()
        self._architecture = ArchitectureHeuristicTool()

    async def run_deterministic_tools(self, ctx: AgentContext) -> list[ToolResult]:
        results: list[ToolResult] = []
        file_tool = FileFetchTool(ctx.github_client)
        files: list[dict] = []

        for pr_file in ctx.diff_files:
            if Path(pr_file.filename).suffix.lstrip(".") != "py":
                continue
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
                {"filename": pr_file.filename, "source": source, "added_lines": []},
            )
            results.append(ast_result)
            files.append(
                {"filename": pr_file.filename, "imports": ast_result.data.get("imports", [])}
            )

        arch_result = await self.call_tool(ctx, self._architecture, {"files": files})
        results.append(arch_result)

        any_signal = bool(arch_result.data.get("architecture_findings"))
        for item in arch_result.data.get("architecture_findings", []):
            await ctx.evidence_store.add(
                review_id=ctx.review_id,
                source="architecture_heuristics",
                agent=self.name,
                tool="architecture_heuristics",
                file=None,
                line=None,
                result=item.get("message", ""),
                confidence=0.7 if item.get("type") == "circular_import" else 0.5,
            )

        results.append(
            ToolResult(
                success=True,
                tool_name="architecture_signal_summary",
                data={"any_signal": any_signal},
            )
        )
        return results

    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        summary = next(tr for tr in tool_results if tr.tool_name == "architecture_signal_summary")
        if summary.data["any_signal"]:
            return True, ""
        return False, "No circular imports or high-coupling hubs found among the changed files"

    async def interpret(
        self, ctx: AgentContext, tool_results: list[ToolResult], llm_text: str | None
    ) -> tuple[list[Finding], ThinkingSummary]:
        findings, reasoning = parse_llm_findings(
            llm_text, review_id=ctx.review_id, detecting_agent=self.name, category="architecture"
        )
        summary = ThinkingSummary(
            objective="Check this PR's changed files for circular imports or high-coupling hubs.",
            decision=(
                "Built an import-dependency graph (networkx) across changed files."
                if llm_text
                else "No architecture signal found; skipped LLM call."
            ),
            action="Parsed imports per changed file and ran cycle/fan-in detection.",
            tool="architecture_heuristics",
            observation=reasoning
            or "No architecture-relevant evidence produced by deterministic tools.",
            next_action="Send findings to Validator." if findings else "No findings to escalate.",
        )
        return findings, summary
