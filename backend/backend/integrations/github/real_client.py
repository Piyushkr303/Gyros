from __future__ import annotations

import base64
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.integrations.github.schemas import (
    PRCommit,
    PRFile,
    PullRequestPayload,
    ReviewPost,
    WorkflowRun,
)

logger = logging.getLogger(__name__)

_API_BASE = "https://api.github.com"


class RealGitHubClient:
    def __init__(self, token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=_API_BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def get_pull_request(self, repo: str, pr_number: int) -> PullRequestPayload:
        pr_resp = await self._client.get(f"/repos/{repo}/pulls/{pr_number}")
        pr_resp.raise_for_status()
        pr = pr_resp.json()

        files = await self.get_pr_files(repo, pr_number)
        commits = await self.get_pr_commits(repo, pr_number)

        return PullRequestPayload(
            number=pr["number"],
            title=pr["title"],
            body=pr.get("body") or "",
            repo=repo,
            head_sha=pr["head"]["sha"],
            base_sha=pr["base"]["sha"],
            author=(pr.get("user") or {}).get("login"),
            files=files,
            commits=commits,
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def get_pr_files(self, repo: str, pr_number: int) -> list[PRFile]:
        resp = await self._client.get(
            f"/repos/{repo}/pulls/{pr_number}/files", params={"per_page": 100}
        )
        resp.raise_for_status()
        return [
            PRFile(
                filename=f["filename"],
                status=f["status"],
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
                changes=f.get("changes", 0),
                patch=f.get("patch"),
            )
            for f in resp.json()
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def get_pr_commits(self, repo: str, pr_number: int) -> list[PRCommit]:
        resp = await self._client.get(
            f"/repos/{repo}/pulls/{pr_number}/commits", params={"per_page": 100}
        )
        resp.raise_for_status()
        return [
            PRCommit(
                sha=c["sha"],
                message=c["commit"]["message"],
                author=(c["commit"].get("author") or {}).get("name"),
            )
            for c in resp.json()
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def get_file_content(self, repo: str, path: str, ref: str) -> str | None:
        resp = await self._client.get(f"/repos/{repo}/contents/{path}", params={"ref": ref})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("encoding") == "base64":
            return base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
        return payload.get("content")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def post_review(self, repo: str, pr_number: int, review: ReviewPost) -> dict:
        resp = await self._client.post(
            f"/repos/{repo}/pulls/{pr_number}/reviews",
            json={
                "body": review.body,
                "event": review.event,
                "comments": [c.model_dump() for c in review.comments],
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def post_issue_comment(self, repo: str, pr_number: int, body: str) -> dict:
        resp = await self._client.post(
            f"/repos/{repo}/issues/{pr_number}/comments", json={"body": body}
        )
        resp.raise_for_status()
        return resp.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def get_workflow_runs(self, repo: str, ref: str) -> list[WorkflowRun]:
        resp = await self._client.get(
            f"/repos/{repo}/actions/runs", params={"head_sha": ref, "per_page": 20}
        )
        resp.raise_for_status()
        return [
            WorkflowRun(
                name=r.get("name") or r.get("workflow_id", "unknown"),
                status=r["status"],
                conclusion=r.get("conclusion"),
                html_url=r.get("html_url"),
            )
            for r in resp.json().get("workflow_runs", [])
        ]
