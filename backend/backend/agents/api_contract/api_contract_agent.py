from __future__ import annotations

from pathlib import Path

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.base_agent import BaseAgent
from backend.core.agents.llm_json import parse_llm_findings
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.finding import Finding
from backend.core.schemas.tool import ToolResult
from backend.tools.ast_tool.python_ast_tool import PythonAstTool
from backend.tools.repository.file_fetch_tool import FileFetchTool


class ApiContractAgent(BaseAgent):
    """Compares each modified Python file's base-vs-head function signatures
    (real AST parse of both refs, not just the diff) and flags parameter-count
    changes on existing public functions as potential breaking API changes for
    callers outside this PR's diff. LLM only interprets ambiguous cases."""

    name = "api_contract_agent"

    def __init__(self) -> None:
        super().__init__()
        self._python_ast = PythonAstTool()

    async def run_deterministic_tools(self, ctx: AgentContext) -> list[ToolResult]:
        results: list[ToolResult] = []
        any_signal = False
        file_tool = FileFetchTool(ctx.github_client)

        for pr_file in ctx.diff_files:
            if Path(pr_file.filename).suffix.lstrip(".") != "py" or pr_file.status != "modified":
                continue

            head_fetch = await self.call_tool(
                ctx,
                file_tool,
                {"repo": ctx.pr.repo, "path": pr_file.filename, "ref": ctx.pr.head_sha},
            )
            results.append(head_fetch)
            base_fetch = await self.call_tool(
                ctx,
                file_tool,
                {"repo": ctx.pr.repo, "path": pr_file.filename, "ref": ctx.pr.base_sha},
            )
            results.append(base_fetch)
            head_source = head_fetch.data.get("content") or ""
            base_source = base_fetch.data.get("content") or ""
            if not head_source or not base_source:
                continue

            head_ast = await self.call_tool(
                ctx,
                self._python_ast,
                {"filename": pr_file.filename, "source": head_source, "added_lines": []},
            )
            results.append(head_ast)
            base_ast = await self.call_tool(
                ctx,
                self._python_ast,
                {"filename": pr_file.filename, "source": base_source, "added_lines": []},
            )
            results.append(base_ast)

            base_funcs = {f["name"]: f for f in base_ast.data.get("functions", [])}
            head_funcs = {f["name"]: f for f in head_ast.data.get("functions", [])}

            for name, head_fn in head_funcs.items():
                if name.startswith("_"):
                    continue
                base_fn = base_funcs.get(name)
                if base_fn is None or base_fn["arg_count"] == head_fn["arg_count"]:
                    continue
                any_signal = True
                await ctx.evidence_store.add(
                    review_id=ctx.review_id,
                    source="python_ast",
                    agent=self.name,
                    tool="python_ast",
                    file=pr_file.filename,
                    line=head_fn["lineno"],
                    result=(
                        f"Public function '{name}' changed its parameter count from {base_fn['arg_count']} "
                        f"to {head_fn['arg_count']} between base and head, a potential breaking change "
                        "for callers outside this PR's diff."
                    ),
                    confidence=0.6,
                )

        results.append(
            ToolResult(
                success=True,
                tool_name="api_contract_signal_summary",
                data={"any_signal": any_signal},
            )
        )
        return results

    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        summary = next(tr for tr in tool_results if tr.tool_name == "api_contract_signal_summary")
        if summary.data["any_signal"]:
            return True, ""
        return False, "No existing public function changed its signature between base and head"

    async def interpret(
        self, ctx: AgentContext, tool_results: list[ToolResult], llm_text: str | None
    ) -> tuple[list[Finding], ThinkingSummary]:
        findings, reasoning = parse_llm_findings(
            llm_text, review_id=ctx.review_id, detecting_agent=self.name, category="api_contract"
        )
        summary = ThinkingSummary(
            objective="Check whether this PR breaks the signature of any existing public function.",
            decision=(
                "Compared base-vs-head AST signatures for modified files."
                if llm_text
                else "No signature changes found; skipped LLM call."
            ),
            action="Parsed base and head file content and diffed function parameter counts by name.",
            tool="python_ast",
            observation=reasoning
            or "No API-contract-relevant evidence produced by deterministic tools.",
            next_action="Send findings to Validator." if findings else "No findings to escalate.",
        )
        return findings, summary
