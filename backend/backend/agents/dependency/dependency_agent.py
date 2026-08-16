from __future__ import annotations

from pathlib import Path

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.base_agent import BaseAgent
from backend.core.agents.llm_json import parse_llm_findings
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.finding import Finding
from backend.core.schemas.tool import ToolResult
from backend.tools.dependency.dependency_heuristic_tool import DependencyHeuristicTool
from backend.tools.dependency.osv_tool import OsvVulnerabilityTool
from backend.tools.diff.diff_parser_tool import DiffParserTool

_DEPENDENCY_FILENAMES = {
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "pipfile",
    "poetry.lock",
}


def _is_dependency_file(filename: str) -> bool:
    name = Path(filename).name.lower()
    return name in _DEPENDENCY_FILENAMES or name.startswith("requirements")


class DependencyAgent(BaseAgent):
    """Runs only when impact_analyzer flags dependency_changed=True (a
    conditionally-activated agent, same pattern the spec describes for a
    database_changed-gated Database Agent). Deterministic requirements.txt
    -style heuristics first; LLM only for ambiguous cases."""

    name = "dependency_agent"

    def __init__(self) -> None:
        super().__init__()
        self._diff_parser = DiffParserTool()
        self._dependency = DependencyHeuristicTool()
        self._osv = OsvVulnerabilityTool()

    async def run_deterministic_tools(self, ctx: AgentContext) -> list[ToolResult]:
        results: list[ToolResult] = []
        any_signal = False

        for pr_file in ctx.diff_files:
            if not _is_dependency_file(pr_file.filename):
                continue

            diff_result = await self.call_tool(
                ctx, self._diff_parser, {"filename": pr_file.filename, "patch": pr_file.patch}
            )
            results.append(diff_result)

            dep_result = await self.call_tool(
                ctx,
                self._dependency,
                {"added_line_texts": diff_result.data.get("added_line_texts", [])},
            )
            results.append(dep_result)
            for item in dep_result.data.get("dependency_findings", []):
                any_signal = True
                await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="dependency_heuristics",
                    agent=self.name,
                    tool="dependency_heuristics",
                    file=pr_file.filename,
                    line=item.get("lineno"),
                    result=item.get("message", ""),
                    confidence=0.75 if item.get("type") == "outdated_dependency" else 0.5,
                )

            osv_result = await self.call_tool(
                ctx, self._osv, {"added_line_texts": diff_result.data.get("added_line_texts", [])}
            )
            results.append(osv_result)
            for vuln in osv_result.data.get("vulnerabilities", []):
                any_signal = True
                await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="osv_vulnerabilities",
                    agent=self.name,
                    tool="osv_vulnerabilities",
                    file=pr_file.filename,
                    line=vuln.get("lineno"),
                    result=(
                        f"OSV {vuln.get('id')}: {vuln['package']}=={vuln['version']} - "
                        f"{vuln.get('summary') or 'known vulnerability'}"
                    ),
                    confidence=0.9,
                )

        results.append(
            ToolResult(
                success=True, tool_name="dependency_signal_summary", data={"any_signal": any_signal}
            )
        )
        return results

    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        summary = next(tr for tr in tool_results if tr.tool_name == "dependency_signal_summary")
        if summary.data["any_signal"]:
            return True, ""
        return False, "No unpinned or outdated dependency signals found in changed dependency files"

    async def interpret(
        self, ctx: AgentContext, tool_results: list[ToolResult], llm_text: str | None
    ) -> tuple[list[Finding], ThinkingSummary]:
        findings, reasoning = parse_llm_findings(
            llm_text, review_id=ctx.review_id, detecting_agent=self.name, category="dependency"
        )
        summary = ThinkingSummary(
            objective="Check changed dependency manifests for unpinned or outdated packages.",
            decision=(
                "Ran requirements.txt-style dependency heuristics."
                if llm_text
                else "No dependency signal found; skipped LLM call."
            ),
            action="Scanned added dependency lines for missing pins, outdated versions, and known OSV vulnerabilities.",
            tool="dependency_heuristics + osv_vulnerabilities",
            observation=reasoning
            or "No dependency-relevant evidence produced by deterministic tools.",
            next_action="Send findings to Validator." if findings else "No findings to escalate.",
        )
        return findings, summary
