from __future__ import annotations

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.base_agent import BaseAgent
from backend.core.agents.llm_json import parse_llm_findings
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.finding import Finding
from backend.core.schemas.tool import ToolResult
from backend.tools.database.database_heuristic_tool import DatabaseHeuristicTool
from backend.tools.repository.file_fetch_tool import FileFetchTool

_DATABASE_HINTS = ("migration", "schema", ".sql", "models.py", "models/")


def _is_database_file(filename: str) -> bool:
    lowered = filename.lower()
    return any(hint in lowered for hint in _DATABASE_HINTS)


class DatabaseAgent(BaseAgent):
    """Runs only when impact_analyzer flags database_changed=True (spec-style
    conditionally-activated agent). Deterministic regex heuristics over
    migration SQL first; LLM only for ambiguous cases."""

    name = "database_agent"

    def __init__(self) -> None:
        super().__init__()
        self._database = DatabaseHeuristicTool()

    async def run_deterministic_tools(self, ctx: AgentContext) -> list[ToolResult]:
        results: list[ToolResult] = []
        any_signal = False

        for pr_file in ctx.diff_files:
            if not _is_database_file(pr_file.filename):
                continue

            file_tool = FileFetchTool(ctx.github_client)
            fetched = await self.call_tool(
                ctx,
                file_tool,
                {"repo": ctx.pr.repo, "path": pr_file.filename, "ref": ctx.pr.head_sha},
            )
            results.append(fetched)
            source = fetched.data.get("content") or ""

            db_result = await self.call_tool(
                ctx, self._database, {"filename": pr_file.filename, "source": source}
            )
            results.append(db_result)
            for item in db_result.data.get("database_findings", []):
                any_signal = True
                await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="database_heuristics",
                    agent=self.name,
                    tool="database_heuristics",
                    file=pr_file.filename,
                    line=item.get("lineno"),
                    result=item.get("message", ""),
                    confidence=0.7 if item.get("type") == "unsafe_not_null_migration" else 0.55,
                )

        results.append(
            ToolResult(
                success=True, tool_name="database_signal_summary", data={"any_signal": any_signal}
            )
        )
        return results

    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        summary = next(tr for tr in tool_results if tr.tool_name == "database_signal_summary")
        if summary.data["any_signal"]:
            return True, ""
        return (
            False,
            "No unsafe migration or missing-rollback signals found in changed database files",
        )

    async def interpret(
        self, ctx: AgentContext, tool_results: list[ToolResult], llm_text: str | None
    ) -> tuple[list[Finding], ThinkingSummary]:
        findings, reasoning = parse_llm_findings(
            llm_text, review_id=ctx.review_id, detecting_agent=self.name, category="database"
        )
        summary = ThinkingSummary(
            objective="Check changed migrations/schema files for unsafe or undocumented database changes.",
            decision=(
                "Ran migration SQL heuristics."
                if llm_text
                else "No database signal found; skipped LLM call."
            ),
            action="Scanned changed database files for unsafe NOT NULL adds and missing rollback plans.",
            tool="database_heuristics",
            observation=reasoning
            or "No database-relevant evidence produced by deterministic tools.",
            next_action="Send findings to Validator." if findings else "No findings to escalate.",
        )
        return findings, summary
