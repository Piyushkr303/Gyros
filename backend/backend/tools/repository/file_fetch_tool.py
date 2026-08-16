from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.tools.base import Tool

if TYPE_CHECKING:
    from backend.integrations.github.client_protocol import GitHubClient


class FileFetchTool(Tool):
    """On-demand context routing (spec §42): agents fetch only the specific
    files they explicitly need (e.g. an authorization middleware referenced
    by a call an agent found), rather than the whole repository."""

    name = "file_fetch"
    description = "Fetch a single file's content from the repository at a given ref."

    def __init__(self, github_client: GitHubClient) -> None:
        self._github_client = github_client

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        repo: str = input["repo"]
        path: str = input["path"]
        ref: str = input["ref"]
        content = await self._github_client.get_file_content(repo, path, ref)
        return {"path": path, "ref": ref, "found": content is not None, "content": content}
