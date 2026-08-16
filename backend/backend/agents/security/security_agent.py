from __future__ import annotations

from pathlib import Path

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.base_agent import BaseAgent
from backend.core.agents.llm_json import parse_llm_findings
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.finding import Finding
from backend.core.schemas.tool import ToolResult
from backend.tools.diff.diff_parser_tool import DiffParserTool
from backend.tools.heuristics.regex_fallback_tool import RegexHeuristicTool
from backend.tools.repository.file_fetch_tool import FileFetchTool
from backend.tools.security.semgrep_tool import SemgrepTool
from backend.tools.security.trivy_tool import TrivyConfigTool

_ANALYZABLE_EXTS = {"py", "js", "ts", "jsx", "tsx", "java", "go", "rb"}


def _is_iac_file(filename: str) -> bool:
    name = Path(filename).name.lower()
    return name.startswith("dockerfile") or "docker-compose" in name


_SEMGREP_SEVERITY_MAP = {"ERROR": "HIGH", "WARNING": "MEDIUM", "INFO": "LOW"}
_REGEX_TYPE_CONFIDENCE = {
    "hardcoded_secret": 0.8,
    "sql_string_building": 0.7,
}


class SecurityAgent(BaseAgent):
    """Investigates authN/authZ, injection, secrets, and other security-sensitive
    changes. Semgrep + regex heuristics run first; the LLM only interprets
    ambiguous or semgrep-unavailable cases (spec §17)."""

    name = "security_agent"

    def __init__(self) -> None:
        super().__init__()
        self._diff_parser = DiffParserTool()
        self._semgrep = SemgrepTool()
        self._regex = RegexHeuristicTool()
        self._trivy = TrivyConfigTool()

    async def run_deterministic_tools(self, ctx: AgentContext) -> list[ToolResult]:
        results: list[ToolResult] = []
        any_signal = False

        for pr_file in ctx.diff_files:
            if _is_iac_file(pr_file.filename):
                file_tool = FileFetchTool(ctx.github_client)
                fetched = await self.call_tool(
                    ctx,
                    file_tool,
                    {"repo": ctx.pr.repo, "path": pr_file.filename, "ref": ctx.pr.head_sha},
                )
                results.append(fetched)
                trivy_result = await self.call_tool(
                    ctx,
                    self._trivy,
                    {"filename": pr_file.filename, "source": fetched.data.get("content") or ""},
                )
                results.append(trivy_result)
                for v in trivy_result.data.get("violations", []):
                    any_signal = True
                    await ctx.evidence_store.add(
                        review_id=ctx.review_id,
                        source="trivy_config",
                        agent=self.name,
                        tool="trivy_config",
                        file=pr_file.filename,
                        line=v.get("lineno"),
                        result=f"[{v.get('id')}] {v.get('title') or v.get('message', '')}",
                        confidence=0.8 if v.get("severity") in ("HIGH", "CRITICAL") else 0.55,
                    )

            ext = Path(pr_file.filename).suffix.lstrip(".")
            if ext not in _ANALYZABLE_EXTS:
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

            semgrep_result = await self.call_tool(
                ctx, self._semgrep, {"filename": pr_file.filename, "source": source}
            )
            results.append(semgrep_result)
            for item in semgrep_result.data.get("results", []):
                any_signal = True
                await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="semgrep",
                    agent=self.name,
                    tool="semgrep",
                    file=pr_file.filename,
                    line=item.get("lineno"),
                    result=f"[{item.get('check_id')}] {item.get('message')}",
                    confidence=0.85
                    if _SEMGREP_SEVERITY_MAP.get(str(item.get("severity")).upper()) == "HIGH"
                    else 0.7,
                )

            regex_result = await self.call_tool(
                ctx,
                self._regex,
                {
                    "filename": pr_file.filename,
                    "added_line_texts": diff_result.data.get("added_line_texts", []),
                    "source": source,
                },
            )
            results.append(regex_result)
            for item in regex_result.data.get("regex_findings", []):
                any_signal = True
                await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="regex_heuristics",
                    agent=self.name,
                    tool="regex_heuristics",
                    file=pr_file.filename,
                    line=item.get("lineno"),
                    result=item.get("message", ""),
                    confidence=_REGEX_TYPE_CONFIDENCE.get(item.get("type", ""), 0.6),
                )
            for fn_name in regex_result.data.get("missing_auth_functions", []):
                any_signal = True
                await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="regex_heuristics",
                    agent=self.name,
                    tool="regex_heuristics",
                    file=pr_file.filename,
                    line=None,
                    result=(
                        f"Sensitive-action function '{fn_name}' has no nearby authorization check "
                        "(authorize/authenticate/require_auth/etc.) in the changed file."
                    ),
                    confidence=0.65,
                )

        results.append(
            ToolResult(
                success=True, tool_name="security_signal_summary", data={"any_signal": any_signal}
            )
        )
        return results

    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        summary = next(tr for tr in tool_results if tr.tool_name == "security_signal_summary")
        if summary.data["any_signal"]:
            return True, ""
        return False, "No semgrep/regex security signals found in the changed files"

    async def interpret(
        self, ctx: AgentContext, tool_results: list[ToolResult], llm_text: str | None
    ) -> tuple[list[Finding], ThinkingSummary]:
        findings, reasoning = parse_llm_findings(
            llm_text, review_id=ctx.review_id, detecting_agent=self.name, category="security"
        )
        summary = ThinkingSummary(
            objective="Investigate security-sensitive changes for auth/injection/secret risks.",
            decision="Ran semgrep and regex heuristics across changed files."
            if llm_text
            else "No security signal found; skipped LLM call.",
            action="Analyzed changed files for security patterns and scanned any changed Dockerfile/docker-compose config with Trivy.",
            tool="semgrep + regex_heuristics + trivy_config",
            observation=reasoning
            or "No security-relevant evidence produced by deterministic tools.",
            next_action="Send findings to Validator." if findings else "No findings to escalate.",
        )
        return findings, summary
