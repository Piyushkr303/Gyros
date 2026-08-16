from __future__ import annotations

import logging
from collections import defaultdict

from backend.core.persistence.repositories import EvidenceRepository
from backend.core.schemas.evidence import Evidence
from backend.core.utils import new_id, now_iso

logger = logging.getLogger(__name__)


class EvidenceStore:
    """Shared evidence store. Agents reference evidence_ids instead of passing
    raw tool/LLM output between each other (spec §39/§42)."""

    def __init__(self, evidence_repository: EvidenceRepository) -> None:
        self._repo = evidence_repository
        self._memory: dict[str, Evidence] = {}
        self._by_review: dict[str, list[str]] = defaultdict(list)

    async def add(
        self,
        *,
        review_id: str,
        source: str,
        agent: str,
        result: str,
        tool: str | None = None,
        file: str | None = None,
        line: int | None = None,
        confidence: float | None = None,
    ) -> Evidence:
        evidence = Evidence(
            evidence_id=new_id("E"),
            review_id=review_id,
            source=source,
            agent=agent,
            tool=tool,
            file=file,
            line=line,
            result=result,
            confidence=confidence,
            timestamp=now_iso(),
        )
        self._memory[evidence.evidence_id] = evidence
        self._by_review[review_id].append(evidence.evidence_id)
        try:
            await self._repo.add(evidence)
        except Exception:  # pragma: no cover
            logger.exception("Failed to persist evidence %s", evidence.evidence_id)
        return evidence

    def get(self, evidence_id: str) -> Evidence | None:
        return self._memory.get(evidence_id)

    def query(
        self, review_id: str, *, file: str | None = None, agent: str | None = None
    ) -> list[Evidence]:
        items = [
            self._memory[eid] for eid in self._by_review.get(review_id, []) if eid in self._memory
        ]
        if file is not None:
            items = [e for e in items if e.file == file]
        if agent is not None:
            items = [e for e in items if e.agent == agent]
        return items
