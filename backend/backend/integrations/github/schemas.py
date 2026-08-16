from __future__ import annotations

from pydantic import BaseModel, Field


class PRFile(BaseModel):
    filename: str
    status: str  # added / modified / removed / renamed
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str | None = None


class PRCommit(BaseModel):
    sha: str
    message: str
    author: str | None = None


class PullRequestPayload(BaseModel):
    number: int
    title: str
    body: str = ""
    repo: str
    head_sha: str
    base_sha: str
    author: str | None = None
    action: str = "synchronize"
    files: list[PRFile] = Field(default_factory=list)
    commits: list[PRCommit] = Field(default_factory=list)


class InlineComment(BaseModel):
    path: str
    line: int
    body: str


class ReviewPost(BaseModel):
    body: str
    event: str = "COMMENT"  # COMMENT / REQUEST_CHANGES / APPROVE
    comments: list[InlineComment] = Field(default_factory=list)


class WorkflowRun(BaseModel):
    name: str
    status: str  # queued / in_progress / completed
    conclusion: str | None = (
        None  # success / failure / cancelled / timed_out / None (not completed)
    )
    html_url: str | None = None
