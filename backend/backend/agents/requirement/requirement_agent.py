from __future__ import annotations

import re
from pathlib import Path

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.base_agent import BaseAgent
from backend.core.agents.llm_json import parse_llm_findings
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.finding import Finding, Severity
from backend.core.schemas.tool import ToolResult
from backend.core.utils import new_id, now_iso
from backend.tools.diff.diff_parser_tool import DiffParserTool
from backend.tools.jira.jira_fetch_tool import JiraFetchTool

_JIRA_KEY_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d+)\b")

_AUTH_CALL_KEYWORDS = (
    "verify_access",
    "verify_permission",
    "authorize(",
    "authenticate(",
    "require_auth",
    "check_permission",
    "has_permission",
    "is_authorized",
)

# Ordered (keywords, rule) pairs: the first matching keyword set classifies an
# acceptance-criterion sentence. Unmatched criteria are ambiguous and go to
# the LLM rather than being guessed at deterministically.
_AC_RULES: list[tuple[tuple[str, ...], str]] = [
    (("test",), "tests"),
    (("log",), "logging"),
    (("verify", "validat", "authoriz", "access", "reject", "denied", "unauthoriz"), "auth"),
]


def _classify_ac(text: str) -> str | None:
    lowered = text.lower()
    for keywords, rule in _AC_RULES:
        if any(k in lowered for k in keywords):
            return rule
    return None


def _rule_satisfied(rule: str, ctx: AgentContext, diff_text: str) -> bool:
    if rule == "tests":
        return ctx.impact.tests_changed
    if rule == "logging":
        return "logger." in diff_text or "log." in diff_text
    if rule == "auth":
        return any(k in diff_text for k in _AUTH_CALL_KEYWORDS)
    return False


class RequirementAgent(BaseAgent):
    """Parses a Jira ticket key from the PR title/body, fetches its
    acceptance criteria (real or mock Jira), and deterministically checks
    each criterion against keyword evidence in the diff text. Criteria that
    can't be auto-classified go to the LLM; unmet criteria become findings
    regardless of whether the LLM was needed, since detecting an unmet
    criterion is itself a deterministic fact once classified."""

    name = "requirement_agent"

    def __init__(self) -> None:
        super().__init__()
        self._diff_parser = DiffParserTool()

    async def run_deterministic_tools(self, ctx: AgentContext) -> list[ToolResult]:
        results: list[ToolResult] = []

        match = _JIRA_KEY_PATTERN.search(f"{ctx.pr.title}\n{ctx.pr.body}")
        if not match:
            results.append(
                ToolResult(
                    success=True,
                    tool_name="requirement_signal_summary",
                    data={"any_signal": False, "unmet": [], "issue_key": None},
                )
            )
            return results

        issue_key = match.group(1)
        jira_tool = JiraFetchTool(ctx.jira_client)
        issue_result = await self.call_tool(ctx, jira_tool, {"key": issue_key})
        results.append(issue_result)
        issue = issue_result.data.get("issue")
        if not issue:
            results.append(
                ToolResult(
                    success=True,
                    tool_name="requirement_signal_summary",
                    data={"any_signal": False, "unmet": [], "issue_key": issue_key},
                )
            )
            return results

        diff_text_parts: list[str] = []
        for pr_file in ctx.diff_files:
            if Path(pr_file.filename).suffix.lstrip(".") != "py":
                continue
            diff_result = await self.call_tool(
                ctx, self._diff_parser, {"filename": pr_file.filename, "patch": pr_file.patch}
            )
            results.append(diff_result)
            diff_text_parts.extend(
                str(e.get("text", "")) for e in diff_result.data.get("added_line_texts", [])
            )
        diff_text = "\n".join(diff_text_parts).lower()

        unmet: list[dict] = []
        ambiguous_count = 0
        for ac in issue.get("acceptance_criteria", []):
            rule = _classify_ac(ac)
            if rule is None:
                ambiguous_count += 1
                await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="jira_acceptance_criteria",
                    agent=self.name,
                    tool="jira_fetch",
                    file=None,
                    line=None,
                    result=f"[{issue_key}] Acceptance criterion could not be auto-classified: '{ac}'",
                    confidence=0.4,
                )
                continue
            if not _rule_satisfied(rule, ctx, diff_text):
                evidence = await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="jira_acceptance_criteria",
                    agent=self.name,
                    tool="jira_fetch",
                    file=None,
                    line=None,
                    result=f"[{issue_key}] Acceptance criterion not evidenced in diff: '{ac}'",
                    confidence=0.6,
                )
                unmet.append({"text": ac, "evidence_id": evidence.evidence_id})

        results.append(
            ToolResult(
                success=True,
                tool_name="requirement_signal_summary",
                data={"any_signal": ambiguous_count > 0, "unmet": unmet, "issue_key": issue_key},
            )
        )
        return results

    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        summary = next(tr for tr in tool_results if tr.tool_name == "requirement_signal_summary")
        if summary.data["any_signal"]:
            return True, ""
        return (
            False,
            "No Jira ticket referenced, or every acceptance criterion was classified deterministically",
        )

    def condition_context(self, findings: list[Finding], tool_results: list[ToolResult]) -> dict:
        base = super().condition_context(findings, tool_results)
        summary = next(
            (tr for tr in tool_results if tr.tool_name == "requirement_signal_summary"), None
        )
        base["issue_key"] = summary.data.get("issue_key") if summary else None
        return base

    async def interpret(
        self, ctx: AgentContext, tool_results: list[ToolResult], llm_text: str | None
    ) -> tuple[list[Finding], ThinkingSummary]:
        summary = next(tr for tr in tool_results if tr.tool_name == "requirement_signal_summary")
        issue_key = summary.data.get("issue_key")
        unmet = summary.data.get("unmet", [])

        now = now_iso()
        deterministic_findings = [
            Finding(
                id=new_id("F"),
                review_id=ctx.review_id,
                severity=Severity.MEDIUM,
                category="requirement",
                file=ctx.diff_files[0].filename if ctx.diff_files else "unknown",
                line=None,
                title=f"{issue_key}: acceptance criterion not evidenced - '{item['text'][:70]}'",
                description=(
                    f"This PR references {issue_key} but the diff does not show keyword evidence that the "
                    f"acceptance criterion '{item['text']}' is satisfied."
                ),
                evidence_ids=[item["evidence_id"]],
                impact="",
                recommendation="Confirm this criterion is actually met, or address it before merging.",
                confidence=0.6,
                detecting_agent=self.name,
                created_at=now,
                updated_at=now,
            )
            for item in unmet
        ]

        llm_findings, reasoning = parse_llm_findings(
            llm_text, review_id=ctx.review_id, detecting_agent=self.name, category="requirement"
        )
        findings = deterministic_findings + llm_findings

        summary_obj = ThinkingSummary(
            objective="Cross-check this PR's diff against its linked Jira ticket's acceptance criteria.",
            decision=(
                f"{issue_key}: {len(unmet)} unmet criterion/criteria found."
                if issue_key
                else "No Jira ticket reference found in the PR title/body."
            ),
            action="Parsed a Jira key from the PR title/body, fetched acceptance criteria, and checked each against diff keywords.",
            tool="jira_fetch + keyword/diff heuristic" + (" + LLM" if llm_text else ""),
            observation=reasoning
            or (
                f"{len(findings)} acceptance-criterion gap(s) found."
                if findings
                else "No gaps found."
            ),
            next_action="Send findings to Validator." if findings else "No findings to escalate.",
        )
        return findings, summary_obj
