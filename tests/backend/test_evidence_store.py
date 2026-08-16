import pytest

from backend.core.evidence.evidence_store import EvidenceStore
from backend.core.persistence.repositories import EvidenceRepository


class _NoopEvidenceRepository(EvidenceRepository):
    def __init__(self):
        pass

    async def add(self, evidence):
        return None


@pytest.fixture
def store():
    return EvidenceStore(_NoopEvidenceRepository())


async def test_add_and_get(store):
    evidence = await store.add(
        review_id="rev-1", source="semgrep", agent="security_agent", result="SQL injection risk", confidence=0.8
    )
    fetched = store.get(evidence.evidence_id)
    assert fetched is not None
    assert fetched.result == "SQL injection risk"


async def test_query_filters_by_agent_and_file(store):
    await store.add(review_id="rev-1", source="ruff", agent="bug_detection_agent", result="lint issue", file="a.py")
    await store.add(review_id="rev-1", source="semgrep", agent="security_agent", result="secret", file="b.py")

    security_only = store.query("rev-1", agent="security_agent")
    assert len(security_only) == 1
    assert security_only[0].file == "b.py"

    by_file = store.query("rev-1", file="a.py")
    assert len(by_file) == 1
    assert by_file[0].agent == "bug_detection_agent"


async def test_query_scoped_to_review(store):
    await store.add(review_id="rev-1", source="ruff", agent="bug_detection_agent", result="x")
    await store.add(review_id="rev-2", source="ruff", agent="bug_detection_agent", result="y")
    assert len(store.query("rev-1")) == 1
    assert len(store.query("rev-2")) == 1
