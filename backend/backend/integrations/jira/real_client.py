from __future__ import annotations

import re

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.integrations.jira.schemas import JiraIssue

_BULLET_LINE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.+)$")


def _extract_text(node: dict) -> str:
    """Best-effort plain-text extraction from Atlassian Document Format (ADF).
    Jira Cloud's issue description is a rich-text tree, not plain text; this
    walks it and joins text nodes, which is good enough for a keyword-based
    acceptance-criteria heuristic (not a full ADF renderer)."""
    if node.get("type") == "text":
        return str(node.get("text", ""))
    parts = [_extract_text(child) for child in node.get("content", [])]
    joined = "".join(parts) if node.get("type") == "text" else " ".join(p for p in parts if p)
    if node.get("type") in ("paragraph", "listItem"):
        return joined + "\n"
    return joined


def _acceptance_criteria_from_description(description: dict | str | None) -> list[str]:
    if not description:
        return []
    text = description if isinstance(description, str) else _extract_text(description)
    criteria = []
    for line in text.splitlines():
        match = _BULLET_LINE.match(line)
        if match:
            criteria.append(match.group(1).strip())
    return criteria


class RealJiraClient:
    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            auth=(email, api_token),
            headers={"Accept": "application/json"},
            timeout=30.0,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def get_issue(self, key: str) -> JiraIssue | None:
        resp = await self._client.get(f"/rest/api/3/issue/{key}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return _issue_from_payload(resp.json())

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def search_issues(self, jql: str, max_results: int = 20) -> list[JiraIssue]:
        resp = await self._client.get(
            "/rest/api/3/search", params={"jql": jql, "maxResults": max_results}
        )
        resp.raise_for_status()
        return [_issue_from_payload(item) for item in resp.json().get("issues", [])]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def add_comment(self, key: str, body: str) -> bool:
        adf_body = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": body}]}],
            }
        }
        resp = await self._client.post(f"/rest/api/3/issue/{key}/comment", json=adf_body)
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def transition_status(self, key: str, status_name: str) -> bool:
        resp = await self._client.get(f"/rest/api/3/issue/{key}/transitions")
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        transitions = resp.json().get("transitions", [])
        match = next(
            (
                t
                for t in transitions
                if (t.get("to") or {}).get("name", "").lower() == status_name.lower()
                or t.get("name", "").lower() == status_name.lower()
            ),
            None,
        )
        if match is None:
            return False
        transition_resp = await self._client.post(
            f"/rest/api/3/issue/{key}/transitions", json={"transition": {"id": match["id"]}}
        )
        transition_resp.raise_for_status()
        return True


def _issue_from_payload(payload: dict) -> JiraIssue:
    fields = payload.get("fields", {})
    return JiraIssue(
        key=payload["key"],
        summary=fields.get("summary", ""),
        status=(fields.get("status") or {}).get("name", ""),
        acceptance_criteria=_acceptance_criteria_from_description(fields.get("description")),
    )
