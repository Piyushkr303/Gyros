from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.integrations.jira.schemas import JiraIssue

logger = logging.getLogger(__name__)


class MockJiraClient:
    """Serves a single local fixture issue (tests/fixtures/demo_pr/jira_issue.json)
    regardless of which key is requested that matches it - mirrors
    MockGitHubClient's single-fixture-PR pattern. Returns None for any other key,
    same as a real 404, so agents see honest "no ticket found" behavior.
    add_comment/transition_status mutate this in-memory fixture rather than
    talking to a real Jira, so the round-trip (comment posted, status changed)
    is observable via get_issue()/search_issues() within the same process,
    same "genuinely stateful but local" contract MockGitHubClient's diffing has."""

    def __init__(self, fixtures_dir: Path) -> None:
        path = fixtures_dir / "jira_issue.json"
        self._issue = (
            JiraIssue(**json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None
        )
        self._comments: list[dict[str, str]] = []

    async def get_issue(self, key: str) -> JiraIssue | None:
        if self._issue is not None and self._issue.key == key:
            logger.info("[MOCK] Jira issue %s served from local fixture", key)
            return self._issue
        return None

    async def search_issues(self, jql: str, max_results: int = 20) -> list[JiraIssue]:
        if self._issue is None:
            return []
        haystack = f"{self._issue.key} {self._issue.summary}".lower()
        needle_hit = any(
            term.strip('"()') in haystack for term in jql.lower().split() if len(term) > 2
        )
        logger.info("[MOCK] Jira search '%s' -> %s", jql, "1 hit" if needle_hit else "0 hits")
        return [self._issue] if needle_hit else []

    async def add_comment(self, key: str, body: str) -> bool:
        if self._issue is None or self._issue.key != key:
            return False
        self._comments.append({"key": key, "body": body})
        logger.info(
            "[MOCK] Comment posted to Jira issue %s: %s", key, body.splitlines()[0] if body else ""
        )
        return True

    async def transition_status(self, key: str, status_name: str) -> bool:
        if self._issue is None or self._issue.key != key:
            return False
        logger.info("[MOCK] Jira issue %s transitioned to '%s'", key, status_name)
        self._issue = self._issue.model_copy(update={"status": status_name})
        return True
