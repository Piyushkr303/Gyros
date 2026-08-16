from __future__ import annotations

from pathlib import Path

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.base_agent import BaseAgent
from backend.core.agents.llm_json import parse_llm_findings
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.finding import Finding
from backend.core.schemas.tool import ToolResult
from backend.tools.accessibility.accessibility_heuristic_tool import AccessibilityHeuristicTool
from backend.tools.lint.eslint_tool import EslintTool
from backend.tools.repository.file_fetch_tool import FileFetchTool

_FRONTEND_EXTS = {"tsx", "jsx", "html", "vue"}
# ESLint (real subprocess, graceful not-installed fallback) only understands
# plain JS/JSX without a TypeScript parser plugin this project doesn't bundle -
# see EslintTool's docstring. .tsx/.html/.vue stay regex-heuristic-only.
_ESLINT_EXTS = {"jsx"}


class AccessibilityAgent(BaseAgent):
    """Runs only when impact_analyzer flags frontend_changed=True. Regex
    heuristics over JSX/TSX/HTML for missing alt text and non-semantic
    clickable elements; LLM only for ambiguous cases."""

    name = "accessibility_agent"

    def __init__(self) -> None:
        super().__init__()
        self._accessibility = AccessibilityHeuristicTool()
        self._eslint = EslintTool()

    async def run_deterministic_tools(self, ctx: AgentContext) -> list[ToolResult]:
        results: list[ToolResult] = []
        any_signal = False

        for pr_file in ctx.diff_files:
            ext = Path(pr_file.filename).suffix.lstrip(".")
            if ext not in _FRONTEND_EXTS:
                continue

            file_tool = FileFetchTool(ctx.github_client)
            fetched = await self.call_tool(
                ctx,
                file_tool,
                {"repo": ctx.pr.repo, "path": pr_file.filename, "ref": ctx.pr.head_sha},
            )
            results.append(fetched)
            source = fetched.data.get("content") or ""

            a11y_result = await self.call_tool(ctx, self._accessibility, {"source": source})
            results.append(a11y_result)
            for item in a11y_result.data.get("accessibility_findings", []):
                any_signal = True
                await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="accessibility_heuristics",
                    agent=self.name,
                    tool="accessibility_heuristics",
                    file=pr_file.filename,
                    line=item.get("lineno"),
                    result=item.get("message", ""),
                    confidence=0.6,
                )

            if ext in _ESLINT_EXTS:
                eslint_result = await self.call_tool(
                    ctx, self._eslint, {"filename": pr_file.filename, "source": source}
                )
                results.append(eslint_result)
                for v in eslint_result.data.get("violations", []):
                    any_signal = True
                    await ctx.evidence_store.add(
                        review_id=ctx.review_id,
                        source="eslint",
                        agent=self.name,
                        tool="eslint",
                        file=pr_file.filename,
                        line=v.get("lineno"),
                        result=f"[{v.get('rule') or 'parse-error'}] {v.get('message', '')}",
                        confidence=0.65 if v.get("severity") == "error" else 0.45,
                    )

        results.append(
            ToolResult(
                success=True,
                tool_name="accessibility_signal_summary",
                data={"any_signal": any_signal},
            )
        )
        return results

    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        summary = next(tr for tr in tool_results if tr.tool_name == "accessibility_signal_summary")
        if summary.data["any_signal"]:
            return True, ""
        return (
            False,
            "No missing-alt or non-semantic-clickable signals found in the changed frontend files",
        )

    async def interpret(
        self, ctx: AgentContext, tool_results: list[ToolResult], llm_text: str | None
    ) -> tuple[list[Finding], ThinkingSummary]:
        findings, reasoning = parse_llm_findings(
            llm_text, review_id=ctx.review_id, detecting_agent=self.name, category="accessibility"
        )
        summary = ThinkingSummary(
            objective="Check changed frontend markup for basic accessibility gaps.",
            decision=(
                "Ran regex-based JSX/TSX/HTML accessibility heuristics."
                if llm_text
                else "No accessibility signal found; skipped LLM call."
            ),
            action="Scanned changed frontend files for missing alt text and non-semantic clickable elements; ran ESLint on plain JSX.",
            tool="accessibility_heuristics + eslint",
            observation=reasoning
            or "No accessibility-relevant evidence produced by deterministic tools.",
            next_action="Send findings to Validator." if findings else "No findings to escalate.",
        )
        return findings, summary
