from __future__ import annotations

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.base_agent import BaseAgent
from backend.core.agents.llm_json import parse_llm_findings
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.finding import Finding, Severity
from backend.core.schemas.tool import ToolResult
from backend.core.utils import new_id, now_iso
from backend.tools.ci.workflow_runs_tool import WorkflowRunsTool

_FAILING_CONCLUSIONS = {"failure", "timed_out", "cancelled", "action_required"}


class CIInvestigatorAgent(BaseAgent):
    """Fetches real CI workflow run results for this PR's head commit and
    deterministically flags any failing check. LLM only interprets runs with
    an ambiguous (still in-progress / no conclusion yet) status."""

    name = "ci_investigator_agent"

    def __init__(self) -> None:
        super().__init__()
        self._runs_tool: WorkflowRunsTool | None = None

    async def run_deterministic_tools(self, ctx: AgentContext) -> list[ToolResult]:
        results: list[ToolResult] = []
        self._runs_tool = WorkflowRunsTool(ctx.github_client)
        runs_result = await self.call_tool(
            ctx, self._runs_tool, {"repo": ctx.pr.repo, "ref": ctx.pr.head_sha}
        )
        results.append(runs_result)

        failed: list[dict] = []
        ambiguous: list[dict] = []
        for run in runs_result.data.get("runs", []):
            conclusion = run.get("conclusion")
            if conclusion in _FAILING_CONCLUSIONS:
                evidence = await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="github_actions",
                    agent=self.name,
                    tool="workflow_runs",
                    file=None,
                    line=None,
                    result=f"CI check '{run.get('name')}' concluded '{conclusion}' ({run.get('html_url')})",
                    confidence=0.9,
                )
                failed.append({**run, "evidence_id": evidence.evidence_id})
            elif run.get("status") != "completed" or conclusion is None:
                await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="github_actions",
                    agent=self.name,
                    tool="workflow_runs",
                    file=None,
                    line=None,
                    result=f"CI check '{run.get('name')}' has ambiguous status='{run.get('status')}' conclusion='{conclusion}'",
                    confidence=0.4,
                )
                ambiguous.append(run)

        results.append(
            ToolResult(
                success=True,
                tool_name="ci_signal_summary",
                data={"any_signal": bool(ambiguous), "failed": failed, "ambiguous": ambiguous},
            )
        )
        return results

    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        summary = next(tr for tr in tool_results if tr.tool_name == "ci_signal_summary")
        if summary.data["any_signal"]:
            return True, ""
        return (
            False,
            "Every CI run has a clear (success/failure) conclusion - no ambiguous runs need judgment",
        )

    async def interpret(
        self, ctx: AgentContext, tool_results: list[ToolResult], llm_text: str | None
    ) -> tuple[list[Finding], ThinkingSummary]:
        summary = next(tr for tr in tool_results if tr.tool_name == "ci_signal_summary")
        failed = summary.data.get("failed", [])

        now = now_iso()
        deterministic_findings = [
            Finding(
                id=new_id("F"),
                review_id=ctx.review_id,
                severity=Severity.HIGH,
                category="ci",
                file=run.get("name", "unknown"),
                line=None,
                title=f"CI check '{run.get('name')}' failed",
                description=(
                    f"The '{run.get('name')}' workflow run concluded '{run.get('conclusion')}' for this PR's "
                    f"head commit. See {run.get('html_url')}."
                ),
                evidence_ids=[run["evidence_id"]] if run.get("evidence_id") else [],
                impact="",
                recommendation="Fix the failing check before this PR is merged.",
                confidence=0.9,
                detecting_agent=self.name,
                created_at=now,
                updated_at=now,
            )
            for run in failed
        ]

        llm_findings, reasoning = parse_llm_findings(
            llm_text, review_id=ctx.review_id, detecting_agent=self.name, category="ci"
        )
        findings = deterministic_findings + llm_findings

        thinking = ThinkingSummary(
            objective="Check real CI workflow run results for this PR's head commit.",
            decision=(
                f"{len(failed)} failing check(s) found."
                if failed
                else "All CI checks completed with a clear conclusion (or none needed judgment)."
            ),
            action="Fetched workflow runs via the GitHub Actions API and classified each by conclusion.",
            tool="workflow_runs" + (" + LLM" if llm_text else ""),
            observation=reasoning
            or (f"{len(findings)} CI finding(s) produced." if findings else "No CI issues found."),
            next_action="Send findings to Validator." if findings else "No findings to escalate.",
        )
        return findings, thinking
