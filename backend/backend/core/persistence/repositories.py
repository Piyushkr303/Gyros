from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlmodel import select

from backend.core.persistence.models import (
    AgentMessageRow,
    EventRow,
    EvidenceRow,
    FindingRow,
    ReviewSessionRow,
    TokenUsageRow,
    ToolResultCacheRow,
)
from backend.core.schemas.events import Event
from backend.core.schemas.evidence import Evidence
from backend.core.schemas.finding import Finding
from backend.core.schemas.message import AgentMessage
from backend.core.schemas.review import ReviewSession
from backend.core.schemas.token_usage import TokenUsageRecord


class _BaseRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory


class ReviewRepository(_BaseRepository):
    async def add(self, review: ReviewSession) -> None:
        async with self._session_factory() as session:
            session.add(ReviewSessionRow.from_domain(review))
            await session.commit()

    async def update(self, review: ReviewSession) -> None:
        async with self._session_factory() as session:
            row = await session.get(ReviewSessionRow, review.review_id)
            if row is None:
                session.add(ReviewSessionRow.from_domain(review))
            else:
                new_row = ReviewSessionRow.from_domain(review)
                for field in ReviewSessionRow.model_fields:
                    setattr(row, field, getattr(new_row, field))
                session.add(row)
            await session.commit()

    async def get(self, review_id: str) -> ReviewSession | None:
        async with self._session_factory() as session:
            row = await session.get(ReviewSessionRow, review_id)
            return row.to_domain() if row else None

    async def list_all(self) -> list[ReviewSession]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ReviewSessionRow).order_by(ReviewSessionRow.created_at.desc())
            )
            return [row.to_domain() for row in result.scalars().all()]

    async def find_latest_by_pr(self, repo: str, pr_number: int) -> ReviewSession | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ReviewSessionRow)
                .where(ReviewSessionRow.repo == repo, ReviewSessionRow.pr_number == pr_number)
                .order_by(ReviewSessionRow.created_at.desc())
            )
            row = result.scalars().first()
            return row.to_domain() if row else None


class FindingRepository(_BaseRepository):
    async def add(self, finding: Finding) -> None:
        async with self._session_factory() as session:
            session.add(FindingRow.from_domain(finding))
            await session.commit()

    async def update(self, finding: Finding) -> None:
        async with self._session_factory() as session:
            row = await session.get(FindingRow, finding.id)
            new_row = FindingRow.from_domain(finding)
            if row is None:
                session.add(new_row)
            else:
                for field in FindingRow.model_fields:
                    setattr(row, field, getattr(new_row, field))
                session.add(row)
            await session.commit()

    async def get(self, finding_id: str) -> Finding | None:
        async with self._session_factory() as session:
            row = await session.get(FindingRow, finding_id)
            return row.to_domain() if row else None

    async def list_by_review(self, review_id: str) -> list[Finding]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(FindingRow)
                .where(FindingRow.review_id == review_id)
                .order_by(FindingRow.created_at)
            )
            return [row.to_domain() for row in result.scalars().all()]


class EvidenceRepository(_BaseRepository):
    async def add(self, evidence: Evidence) -> None:
        async with self._session_factory() as session:
            session.add(EvidenceRow.from_domain(evidence))
            await session.commit()

    async def get(self, evidence_id: str) -> Evidence | None:
        async with self._session_factory() as session:
            row = await session.get(EvidenceRow, evidence_id)
            return row.to_domain() if row else None

    async def list_by_review(self, review_id: str) -> list[Evidence]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(EvidenceRow)
                .where(EvidenceRow.review_id == review_id)
                .order_by(EvidenceRow.timestamp)
            )
            return [row.to_domain() for row in result.scalars().all()]


class EventRepository(_BaseRepository):
    async def add(self, event: Event) -> None:
        async with self._session_factory() as session:
            session.add(EventRow.from_domain(event))
            await session.commit()

    async def list_by_review(self, review_id: str) -> list[Event]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(EventRow).where(EventRow.review_id == review_id).order_by(EventRow.timestamp)
            )
            return [row.to_domain() for row in result.scalars().all()]


class TokenUsageRepository(_BaseRepository):
    async def add(self, record: TokenUsageRecord) -> None:
        async with self._session_factory() as session:
            session.add(TokenUsageRow.from_domain(record))
            await session.commit()

    async def list_by_review(self, review_id: str) -> list[TokenUsageRecord]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(TokenUsageRow)
                .where(TokenUsageRow.review_id == review_id)
                .order_by(TokenUsageRow.timestamp)
            )
            return [row.to_domain() for row in result.scalars().all()]


class ToolResultCacheRepository(_BaseRepository):
    async def get(self, cache_key: str) -> ToolResultCacheRow | None:
        async with self._session_factory() as session:
            return await session.get(ToolResultCacheRow, cache_key)

    async def add(self, row: ToolResultCacheRow) -> None:
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()

    async def increment_hit(self, cache_key: str) -> None:
        async with self._session_factory() as session:
            row = await session.get(ToolResultCacheRow, cache_key)
            if row is not None:
                row.hit_count += 1
                session.add(row)
                await session.commit()


class AgentMessageRepository(_BaseRepository):
    async def add(self, message: AgentMessage) -> None:
        async with self._session_factory() as session:
            session.add(AgentMessageRow.from_domain(message))
            await session.commit()

    async def list_by_review(self, review_id: str) -> list[AgentMessage]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AgentMessageRow)
                .where(AgentMessageRow.review_id == review_id)
                .order_by(AgentMessageRow.timestamp)
            )
            return [row.to_domain() for row in result.scalars().all()]
