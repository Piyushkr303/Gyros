from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.tools.base import Tool

if TYPE_CHECKING:
    from backend.integrations.github.client_protocol import GitHubClient


class WorkflowRunsTool(Tool):
    """Fetches CI workflow run results for this PR's head commit. GitHub
    Actions is part of the GitHub REST API, so this reuses the same
    real/mock GitHub client and token - no separate integration needed."""

    name = "workflow_runs"
    description = "Fetch CI workflow run results for a commit ref."

    def __init__(self, github_client: GitHubClient) -> None:
        self._github_client = github_client

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        repo: str = input["repo"]
        ref: str = input["ref"]
        runs = await self._github_client.get_workflow_runs(repo, ref)
        return {"runs": [r.model_dump() for r in runs]}
