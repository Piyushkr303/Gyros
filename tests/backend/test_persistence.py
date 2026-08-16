import pytest

from backend.core.persistence.db import dispose_db, get_session_factory, init_db
from backend.core.persistence.repositories import EvidenceRepository, FindingRepository, ReviewRepository
from backend.core.schemas.evidence import Evidence
from backend.core.schemas.finding import Finding, Severity, ValidationStatus
from backend.core.schemas.review import ReviewSession, ReviewStatus
from backend.core.utils import now_iso


@pytest.fixture
async def session_factory(tmp_path):
    db_path = tmp_path / "test.db"
    await init_db(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    yield get_session_factory()
    await dispose_db()


async def test_review_repository_round_trip(session_factory):
    repo = ReviewRepository(session_factory)
    session = ReviewSession(
        review_id="rev-1",
        pr_number=1,
        repo="org/repo",
        status=ReviewStatus.RECEIVED,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    await repo.add(session)

    fetched = await repo.get("rev-1")
    assert fetched is not None
    assert fetched.pr_number == 1

    session.status = ReviewStatus.PUBLISHED
    await repo.update(session)
    updated = await repo.get("rev-1")
    assert updated.status == ReviewStatus.PUBLISHED


async def test_finding_repository_round_trip(session_factory):
    repo = FindingRepository(session_factory)
    now = now_iso()
    finding = Finding(
        id="F-1",
        review_id="rev-1",
        severity=Severity.HIGH,
        category="security",
        file="a.py",
        line=10,
        title="Missing auth check",
        description="No authorization check before charging.",
        evidence_ids=["E-1"],
        confidence=0.9,
        detecting_agent="security_agent",
        created_at=now,
        updated_at=now,
    )
    await repo.add(finding)

    fetched = await repo.get("F-1")
    assert fetched is not None
    assert fetched.evidence_ids == ["E-1"]

    finding.validator_status = ValidationStatus.CONFIRMED
    await repo.update(finding)
    updated = await repo.get("F-1")
    assert updated.validator_status == ValidationStatus.CONFIRMED

    by_review = await repo.list_by_review("rev-1")
    assert len(by_review) == 1


async def test_evidence_repository_round_trip(session_factory):
    repo = EvidenceRepository(session_factory)
    evidence = Evidence(
        evidence_id="E-1",
        review_id="rev-1",
        source="semgrep",
        agent="security_agent",
        result="Hardcoded secret",
        timestamp=now_iso(),
    )
    await repo.add(evidence)
    fetched = await repo.get("E-1")
    assert fetched is not None
    assert fetched.source == "semgrep"

    by_review = await repo.list_by_review("rev-1")
    assert len(by_review) == 1
