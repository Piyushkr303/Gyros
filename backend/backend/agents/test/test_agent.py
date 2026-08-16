from __future__ import annotations

from pathlib import Path

from backend.config.settings import get_settings
from backend.core.agents.agent_context import AgentContext
from backend.core.agents.base_agent import BaseAgent
from backend.core.agents.llm_json import parse_llm_findings
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.finding import Finding
from backend.core.schemas.tool import ToolResult
from backend.tools.repository.file_fetch_tool import FileFetchTool
from backend.tools.test_runner.pytest_tool import PytestTool
from backend.tools.test_runner.test_static_tool import TestStaticHeuristicTool


def _candidate_test_paths(filename: str) -> list[str]:
    p = Path(filename)
    name = p.name
    parent = str(p.parent) if str(p.parent) != "." else ""
    candidates = [f"test_{name}", f"tests/test_{name}"]
    if parent:
        candidates.append(f"{parent}/test_{name}")
        candidates.append(f"{parent}/tests/test_{name}")
    return candidates


class TestAgent(BaseAgent):
    """Analyzes existing/missing test coverage for the diff, and (when
    explicitly enabled) actually runs pytest against an isolated temp copy of
    the changed + test files (spec §19)."""

    name = "test_agent"

    def __init__(self) -> None:
        super().__init__()
        self._static = TestStaticHeuristicTool()

    async def run_deterministic_tools(self, ctx: AgentContext) -> list[ToolResult]:
        results: list[ToolResult] = []
        settings = get_settings()
        file_tool = FileFetchTool(ctx.github_client)

        test_files: list[dict] = []
        source_files: dict[str, str] = {}

        for pr_file in ctx.diff_files:
            if Path(pr_file.filename).suffix.lstrip(".") != "py":
                continue
            is_test = "test_" in Path(pr_file.filename).name or "/tests/" in pr_file.filename

            fetched = await self.call_tool(
                ctx,
                file_tool,
                {"repo": ctx.pr.repo, "path": pr_file.filename, "ref": ctx.pr.head_sha},
            )
            results.append(fetched)
            content = fetched.data.get("content") or ""
            if not content:
                continue

            if is_test:
                test_files.append({"filename": pr_file.filename, "source": content})
            else:
                source_files[pr_file.filename] = content
                for candidate in _candidate_test_paths(pr_file.filename):
                    candidate_fetch = await self.call_tool(
                        ctx,
                        file_tool,
                        {"repo": ctx.pr.repo, "path": candidate, "ref": ctx.pr.head_sha},
                    )
                    results.append(candidate_fetch)
                    if candidate_fetch.data.get("found"):
                        test_files.append(
                            {
                                "filename": candidate,
                                "source": candidate_fetch.data.get("content") or "",
                            }
                        )
                        break

        static_result = await self.call_tool(
            ctx,
            self._static,
            {"test_files": test_files, "changed_function_names": ctx.impact.changed_functions},
        )
        results.append(static_result)

        for fn_name in static_result.data.get("uncovered_functions", []):
            await ctx.evidence_store.add(
                review_id=ctx.review_id,
                source="test_static_heuristic",
                agent=self.name,
                tool="test_static_heuristic",
                file=None,
                line=None,
                result=f"Changed function '{fn_name}' has no apparent test reference in {len(test_files)} test file(s).",
                confidence=0.6,
            )

        if settings.enable_test_execution and test_files and source_files:
            pytest_tool = PytestTool(enabled=True)
            files = {**source_files, **{tf["filename"]: tf["source"] for tf in test_files}}
            pytest_result = await self.call_tool(ctx, pytest_tool, {"files": files})
            results.append(pytest_result)
            if pytest_result.data.get("executed") and pytest_result.data.get("tests_failed", 0) > 0:
                for failed in pytest_result.data.get("failed_tests", []):
                    await ctx.evidence_store.add(
                        review_id=ctx.review_id,
                        source="pytest",
                        agent=self.name,
                        tool="pytest_runner",
                        file=None,
                        line=None,
                        result=f"Test failed: {failed.get('nodeid')}",
                        confidence=0.95,
                    )

        return results

    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        static_result = next(tr for tr in tool_results if tr.tool_name == "test_static_heuristic")
        uncovered = static_result.data.get("uncovered_functions", [])
        pytest_result = next((tr for tr in tool_results if tr.tool_name == "pytest_runner"), None)
        tests_failed = bool(pytest_result and pytest_result.data.get("tests_failed", 0) > 0)
        if uncovered or tests_failed:
            return True, ""
        return False, "All changed functions appear referenced by tests; no failures detected"

    async def interpret(
        self, ctx: AgentContext, tool_results: list[ToolResult], llm_text: str | None
    ) -> tuple[list[Finding], ThinkingSummary]:
        findings, reasoning = parse_llm_findings(
            llm_text, review_id=ctx.review_id, detecting_agent=self.name, category="testing"
        )
        summary = ThinkingSummary(
            objective="Determine whether the diff has adequate test coverage and passing tests.",
            decision="Correlated changed functions against test file contents."
            if llm_text
            else "Coverage looks adequate; skipped LLM call.",
            action="Located candidate test files and ran static coverage correlation.",
            tool="test_static_heuristic"
            + (" + pytest_runner" if get_settings().enable_test_execution else ""),
            observation=reasoning or "No test-coverage gaps or failures found.",
            next_action="Send findings to Validator." if findings else "No findings to escalate.",
        )
        return findings, summary
