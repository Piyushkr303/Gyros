from __future__ import annotations

import difflib
import json
import logging
from pathlib import Path

from backend.integrations.github.schemas import (
    PRCommit,
    PRFile,
    PullRequestPayload,
    ReviewPost,
    WorkflowRun,
)

logger = logging.getLogger(__name__)


def _unified_patch(base_text: str, head_text: str) -> str:
    """Real diff computation (difflib), just sourced from local fixture files
    instead of a live git repository."""
    base_lines = base_text.splitlines()
    head_lines = head_text.splitlines()
    diff_lines = list(difflib.unified_diff(base_lines, head_lines, lineterm=""))
    # Drop the '---'/'+++' file header lines; DiffParserTool supplies its own,
    # since PRFile.patch is expected to be hunk-only (as GitHub's API returns it).
    hunk_lines = [line for line in diff_lines if not line.startswith(("---", "+++"))]
    return "\n".join(hunk_lines)


class MockGitHubClient:
    """Serves the local demo PR fixture (tests/fixtures/demo_pr/) as if it
    were a real GitHub API response. Diffs are computed for real via difflib
    at request time - nothing here is a pre-baked fake response.

    Supports a second "revision" (pr_meta_followup.json/manifest_followup.json,
    if present) representing a follow-up push to the same PR, so incremental
    review has something real to demo: get_pull_request()/get_pr_files()
    always reflect whichever revision is "current" - exactly how a real
    GitHub API always returns the PR's current base...head diff, never a
    specific historical push - and trigger-demo-followup advances it."""

    def __init__(self, fixtures_dir: Path) -> None:
        self._dir = fixtures_dir
        self._revisions: list[dict] = [self._load_revision("pr_meta.json", "manifest.json")]
        if (fixtures_dir / "pr_meta_followup.json").exists():
            self._revisions.append(
                self._load_revision("pr_meta_followup.json", "manifest_followup.json")
            )
        self._revision_index = 0

        ci_path = fixtures_dir / "ci_runs.json"
        self._ci_runs = (
            json.loads(ci_path.read_text(encoding="utf-8"))["runs"] if ci_path.exists() else []
        )

    def _load_revision(self, meta_name: str, manifest_name: str) -> dict:
        return {
            "meta": json.loads((self._dir / meta_name).read_text(encoding="utf-8")),
            "manifest": json.loads((self._dir / manifest_name).read_text(encoding="utf-8")),
        }

    @property
    def _meta(self) -> dict:
        return self._revisions[self._revision_index]["meta"]

    @property
    def _manifest(self) -> dict:
        return self._revisions[self._revision_index]["manifest"]

    def has_followup_revision(self) -> bool:
        return len(self._revisions) > 1

    def advance_revision(self) -> None:
        if self._revision_index < len(self._revisions) - 1:
            self._revision_index += 1

    def reset_revision(self) -> None:
        self._revision_index = 0

    def _read(self, filename: str | None) -> str:
        if not filename:
            return ""
        path = self._dir / filename
        return path.read_text(encoding="utf-8") if path.exists() else ""

    async def get_pull_request(self, repo: str, pr_number: int) -> PullRequestPayload:
        files = await self.get_pr_files(repo, pr_number)
        commits = await self.get_pr_commits(repo, pr_number)
        return PullRequestPayload(
            number=self._meta["number"],
            title=self._meta["title"],
            body=self._meta.get("body", ""),
            repo=self._meta["repo"],
            head_sha=self._meta["head_sha"],
            base_sha=self._meta["base_sha"],
            author=self._meta.get("author"),
            action=self._meta.get("action", "synchronize"),
            files=files,
            commits=commits,
        )

    async def get_pr_files(self, repo: str, pr_number: int) -> list[PRFile]:
        result: list[PRFile] = []
        for entry in self._manifest["files"]:
            base_text = "" if entry["status"] == "added" else self._read(entry.get("base_file"))
            head_text = "" if entry["status"] == "removed" else self._read(entry.get("head_file"))
            patch = _unified_patch(base_text, head_text)
            additions = sum(1 for line in patch.splitlines() if line.startswith("+"))
            deletions = sum(1 for line in patch.splitlines() if line.startswith("-"))
            result.append(
                PRFile(
                    filename=entry["filename"],
                    status=entry["status"],
                    additions=additions,
                    deletions=deletions,
                    changes=additions + deletions,
                    patch=patch,
                )
            )
        return result

    async def get_pr_commits(self, repo: str, pr_number: int) -> list[PRCommit]:
        return [
            PRCommit(sha=c["sha"], message=c["message"], author=c.get("author"))
            for c in self._meta.get("commits", [])
        ]

    async def get_file_content(self, repo: str, path: str, ref: str) -> str | None:
        # Searches every revision (not just the current one) so a ref from
        # an earlier push still resolves correctly - e.g. Code Explorer on
        # an older, already-published review shouldn't break just because
        # the fixture has since "advanced" to a follow-up push.
        for revision in self._revisions:
            meta, manifest = revision["meta"], revision["manifest"]
            if ref not in (meta["head_sha"], meta["base_sha"]):
                continue
            for entry in manifest["files"]:
                if entry["filename"] != path:
                    continue
                if ref == meta["head_sha"]:
                    content = (
                        "" if entry["status"] == "removed" else self._read(entry.get("head_file"))
                    )
                else:
                    content = (
                        "" if entry["status"] == "added" else self._read(entry.get("base_file"))
                    )
                if content:
                    return content
            for entry in manifest.get("context_files", []):
                if entry["filename"] == path:
                    return self._read(entry["file"]) or None
        return None

    async def post_review(self, repo: str, pr_number: int, review: ReviewPost) -> dict:
        logger.info(
            "[MOCK] GitHub review posted for %s#%s: %s (%d inline comment(s))",
            repo,
            pr_number,
            review.event,
            len(review.comments),
        )
        for comment in review.comments:
            logger.info(
                "[MOCK]   %s:%s -> %s", comment.path, comment.line, comment.body.splitlines()[0]
            )
        return {
            "id": "mock-review-1",
            "state": review.event,
            "body": review.body,
            "comment_count": len(review.comments),
        }

    async def post_issue_comment(self, repo: str, pr_number: int, body: str) -> dict:
        logger.info("[MOCK] GitHub issue comment posted for %s#%s", repo, pr_number)
        return {"id": "mock-comment-1", "body": body}

    async def get_workflow_runs(self, repo: str, ref: str) -> list[WorkflowRun]:
        return [
            WorkflowRun(
                name=r["name"],
                status=r["status"],
                conclusion=r.get("conclusion"),
                html_url=r.get("html_url"),
            )
            for r in self._ci_runs
        ]
