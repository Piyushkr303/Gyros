from __future__ import annotations

from typing import Protocol

from backend.integrations.jira.schemas import JiraIssue


class JiraClient(Protocol):
    async def get_issue(self, key: str) -> JiraIssue | None: ...

    async def search_issues(self, jql: str, max_results: int = 20) -> list[JiraIssue]: ...

    async def add_comment(self, key: str, body: str) -> bool: ...

    async def transition_status(self, key: str, status_name: str) -> bool: ...
