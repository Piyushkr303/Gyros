from __future__ import annotations

from typing import Protocol

from backend.integrations.github.schemas import (
    PRCommit,
    PRFile,
    PullRequestPayload,
    ReviewPost,
    WorkflowRun,
)


class GitHubClient(Protocol):
    async def get_pull_request(self, repo: str, pr_number: int) -> PullRequestPayload: ...

    async def get_pr_files(self, repo: str, pr_number: int) -> list[PRFile]: ...

    async def get_pr_commits(self, repo: str, pr_number: int) -> list[PRCommit]: ...

    async def get_file_content(self, repo: str, path: str, ref: str) -> str | None: ...

    async def post_review(self, repo: str, pr_number: int, review: ReviewPost) -> dict: ...

    async def post_issue_comment(self, repo: str, pr_number: int, body: str) -> dict: ...

    async def get_workflow_runs(self, repo: str, ref: str) -> list[WorkflowRun]: ...
