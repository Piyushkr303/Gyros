from __future__ import annotations

from pathlib import Path

from backend.core.agents.agent_context import AgentContext
from backend.core.agents.base_agent import BaseAgent
from backend.core.schemas.agent_state import ThinkingSummary
from backend.core.schemas.finding import Finding
from backend.core.schemas.tool import ToolResult
from backend.tools.ast_tool.python_ast_tool import PythonAstTool
from backend.tools.diff.diff_parser_tool import DiffParserTool
from backend.tools.repository.file_fetch_tool import FileFetchTool

_FRONTEND_EXTS = {"tsx", "jsx", "ts", "js", "css", "scss", "html", "vue"}
_FRONTEND_PATH_HINTS = ("frontend/", "components/", "pages/", "ui/")
_BACKEND_EXTS = {"py", "java", "go", "rb", "cs"}
_BACKEND_PATH_HINTS = ("backend/", "server/", "service/")
_DATABASE_HINTS = ("migration", "schema", ".sql", "models.py", "models/")
_API_HINTS = ("api/", "routes/", "route.py", "controller", "endpoint")
_SECURITY_HINTS = ("auth", "security", "payment", "password", "token", "permission", "crypto")
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


def _matches_any(text: str, hints: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in hints)


class ImpactAnalyzerAgent(BaseAgent):
    """Deterministic-only agent (spec §14). Never calls the LLM: path/extension
    heuristics + real Python AST analysis of touched functions/imports."""

    name = "impact_analyzer"

    def __init__(self) -> None:
        super().__init__()
        self._diff_parser = DiffParserTool()
        self._python_ast = PythonAstTool()

    async def run_deterministic_tools(self, ctx: AgentContext) -> list[ToolResult]:
        results: list[ToolResult] = []

        frontend_changed = False
        backend_changed = False
        database_changed = False
        api_changed = False
        security_sensitive = False
        tests_changed = False
        dependency_changed = False
        changed_files: list[dict] = []
        changed_functions: list[str] = []
        changed_imports: list[str] = []
        reasons: dict[str, str] = {}

        for pr_file in ctx.diff_files:
            filename = pr_file.filename
            ext = Path(filename).suffix.lstrip(".")
            is_test = (
                "test_" in Path(filename).name or "/tests/" in filename or "_test." in filename
            )

            changed_files.append(
                {
                    "filename": filename,
                    "status": pr_file.status,
                    "additions": pr_file.additions,
                    "deletions": pr_file.deletions,
                    "extension": ext,
                    "is_test": is_test,
                }
            )

            if is_test:
                tests_changed = True

            if ext in _FRONTEND_EXTS or _matches_any(filename, _FRONTEND_PATH_HINTS):
                frontend_changed = True
                reasons.setdefault(
                    "frontend_changed", f"{filename} matches frontend extension/path"
                )
            if ext in _BACKEND_EXTS or _matches_any(filename, _BACKEND_PATH_HINTS):
                backend_changed = True
                reasons.setdefault("backend_changed", f"{filename} matches backend extension/path")
            if _matches_any(filename, _DATABASE_HINTS):
                database_changed = True
                reasons.setdefault("database_changed", f"{filename} matches database-related path")
            if _matches_any(filename, _API_HINTS):
                api_changed = True
                reasons.setdefault("api_changed", f"{filename} matches API-related path")
            if _matches_any(filename, _SECURITY_HINTS):
                security_sensitive = True
                reasons.setdefault(
                    "security_sensitive", f"{filename} matches security-sensitive path"
                )
            if _is_dependency_file(filename):
                dependency_changed = True
                reasons.setdefault("dependency_changed", f"{filename} is a dependency manifest")

            diff_result = await self.call_tool(
                ctx, self._diff_parser, {"filename": filename, "patch": pr_file.patch}
            )
            results.append(diff_result)

            if ext == "py" and diff_result.success:
                file_tool = FileFetchTool(ctx.github_client)
                fetched = await self.call_tool(
                    ctx, file_tool, {"repo": ctx.pr.repo, "path": filename, "ref": ctx.pr.head_sha}
                )
                results.append(fetched)
                source = fetched.data.get("content") or ""
                if source:
                    ast_result = await self.call_tool(
                        ctx,
                        self._python_ast,
                        {
                            "filename": filename,
                            "source": source,
                            "added_lines": diff_result.data.get("added_lines", []),
                        },
                    )
                    results.append(ast_result)
                    changed_functions.extend(
                        f["name"] for f in ast_result.data.get("touched_functions", [])
                    )
                    changed_imports.extend(ast_result.data.get("imports", []))
                    if not security_sensitive and _matches_any(
                        " ".join(ast_result.data.get("imports", [])), _SECURITY_HINTS
                    ):
                        security_sensitive = True
                        reasons.setdefault(
                            "security_sensitive", f"{filename} imports security-related modules"
                        )

        impact_data = {
            "frontend_changed": frontend_changed,
            "backend_changed": backend_changed,
            "database_changed": database_changed,
            "api_changed": api_changed,
            "security_sensitive": security_sensitive,
            "tests_changed": tests_changed,
            "dependency_changed": dependency_changed,
            "changed_files": changed_files,
            "changed_functions": sorted(set(changed_functions)),
            "changed_imports": sorted(set(changed_imports)),
            "reasons": reasons,
        }
        results.append(ToolResult(success=True, tool_name="impact_summary", data=impact_data))
        return results

    def needs_llm(self, tool_results: list[ToolResult]) -> tuple[bool, str]:
        return (
            False,
            "Impact analysis is purely deterministic path/extension/AST heuristics (spec §14)",
        )

    async def interpret(
        self, ctx: AgentContext, tool_results: list[ToolResult], llm_text: str | None
    ) -> tuple[list[Finding], ThinkingSummary]:
        impact_data = next(tr.data for tr in tool_results if tr.tool_name == "impact_summary")
        touched = ", ".join(impact_data["changed_functions"][:5]) or "none"
        summary = ThinkingSummary(
            objective="Determine which parts of the system this PR touches before running specialized agents.",
            decision="Classified changed files by path/extension and parsed touched Python functions via AST.",
            action="Ran diff parsing and AST analysis on every changed file.",
            tool="diff_parser + python_ast",
            observation=(
                f"{len(impact_data['changed_files'])} file(s) changed; "
                f"security_sensitive={impact_data['security_sensitive']}; touched functions: {touched}"
            ),
            next_action="Route to Security/Bug/Test agents based on these impact flags.",
        )
        return [], summary

    def condition_context(self, findings: list[Finding], tool_results: list[ToolResult]) -> dict:
        impact_data = next(tr.data for tr in tool_results if tr.tool_name == "impact_summary")
        return impact_data
