from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.tools.base import Tool

if TYPE_CHECKING:
    from backend.integrations.jira.client_protocol import JiraClient


class JiraFetchTool(Tool):
    """Fetches a single Jira issue (summary, status, acceptance criteria) by
    key, so the Requirement Agent can cross-check a PR's diff against it."""

    name = "jira_fetch"
    description = "Fetch a Jira issue's acceptance criteria by key."

    def __init__(self, jira_client: JiraClient) -> None:
        self._jira_client = jira_client

    async def _run(self, input: dict[str, Any]) -> dict[str, Any]:
        key: str = input["key"]
        issue = await self._jira_client.get_issue(key)
        return {
            "key": key,
            "found": issue is not None,
            "issue": issue.model_dump() if issue else None,
        }
