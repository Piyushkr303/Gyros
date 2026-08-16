from __future__ import annotations

import logging
from collections import defaultdict

from backend.core.persistence.repositories import FindingRepository
from backend.core.schemas.finding import Finding

logger = logging.getLogger(__name__)


class FindingStore:
    """In-memory + SQLite-backed index of findings for a review, shared across
    the Validator/Critic/Final Review agents and the API layer."""

    def __init__(self, finding_repository: FindingRepository) -> None:
        self._repo = finding_repository
        self._memory: dict[str, Finding] = {}
        self._by_review: dict[str, list[str]] = defaultdict(list)

    async def add(self, finding: Finding) -> None:
        self._memory[finding.id] = finding
        if finding.id not in self._by_review[finding.review_id]:
            self._by_review[finding.review_id].append(finding.id)
        try:
            await self._repo.add(finding)
        except Exception:  # pragma: no cover
            logger.exception("Failed to persist finding %s", finding.id)

    async def update(self, finding: Finding) -> None:
        self._memory[finding.id] = finding
        try:
            await self._repo.update(finding)
        except Exception:  # pragma: no cover
            logger.exception("Failed to persist finding update %s", finding.id)

    def get(self, finding_id: str) -> Finding | None:
        return self._memory.get(finding_id)

    async def list_by_review(self, review_id: str) -> list[Finding]:
        if review_id in self._by_review:
            return [self._memory[fid] for fid in self._by_review[review_id] if fid in self._memory]
        # Not seen by this process (e.g. after a restart) - fall back to SQLite.
        findings = await self._repo.list_by_review(review_id)
        for f in findings:
            self._memory[f.id] = f
            self._by_review[review_id].append(f.id)
        return findings
