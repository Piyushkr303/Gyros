from pathlib import Path

import pytest

from backend.agents.debate.debate_agent import DebateAgent
from backend.core.agents.agent_context import AgentContext
from backend.core.communication.message_bus import MessageBus
from backend.core.evidence.evidence_store import EvidenceStore
from backend.core.events.event_bus import EventBus
from backend.core.findings.finding_store import FindingStore
from backend.core.persistence.db import dispose_db, get_session_factory, init_db
from backend.core.persistence.repositories import (
    AgentMessageRepository,
    EventRepository,
    EvidenceRepository,
    FindingRepository,
    TokenUsageRepository,
)
from backend.core.schemas.finding import CriticStatus, Finding, Severity, ValidationStatus
from backend.core.schemas.impact import ImpactAnalysisResult
from backend.core.utils import new_id, now_iso
from backend.integrations.github.mock_client import MockGitHubClient
from backend.integrations.jira.mock_client import MockJiraClient
from backend.llm.groq.mock_provider import MockGroqProvider
from backend.llm.routing.token_budget import TokenBudget

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "demo_pr"


def _finding(**overrides) -> Finding:
    now = now_iso()
    base = dict(
        id=new_id("F"),
        review_id="rev-debate-test",
        severity=Severity.LOW,
        category="security",
        file="payment_service.py",
        line=24,
        title="Some finding",
        description="Some description",
        detecting_agent="security_agent",
        confidence=0.7,
        validator_status=ValidationStatus.CONFIRMED,
        critic_status=CriticStatus.ACCEPTED,
        created_at=now,
        updated_at=now,
    )
    base.update(overrides)
    return Finding(**base)


@pytest.fixture
async def ctx(tmp_path):
    db_path = tmp_path / "test.db"
    await init_db(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    session_factory = get_session_factory()

    event_bus = EventBus(EventRepository(session_factory))
    evidence_store = EvidenceStore(EvidenceRepository(session_factory))
    finding_store = FindingStore(FindingRepository(session_factory))
    message_bus = MessageBus(event_bus, AgentMessageRepository(session_factory))
    github_client = MockGitHubClient(FIXTURES_DIR)
    jira_client = MockJiraClient(FIXTURES_DIR)
    pr = await github_client.get_pull_request("demo-org/demo-payments", 238)

    context = AgentContext(
        review_id="rev-debate-test",
        pr=pr,
        diff_files=pr.files,
        impact=ImpactAnalysisResult(),
        evidence_store=evidence_store,
        finding_store=finding_store,
        token_usage_repository=TokenUsageRepository(session_factory),
        event_bus=event_bus,
        message_bus=message_bus,
        github_client=github_client,
        jira_client=jira_client,
        llm=MockGroqProvider(),
        token_budget=TokenBudget(),
    )
    yield context
    await dispose_db()


async def test_debate_resolves_same_category_conflict_to_more_severe(ctx):
    low = _finding(severity=Severity.LOW, category="security", title="Minor issue", detecting_agent="security_agent")
    high = _finding(
        id=new_id("F"), severity=Severity.CRITICAL, category="security", title="Serious issue", detecting_agent="bug_detection_agent"
    )
    for f in (low, high):
        await ctx.finding_store.add(f)

    result = await DebateAgent().run(ctx, [low, high], conflict_clusters=[[low.id, high.id]])

    assert result.llm_calls_made == 1
    assert low.severity == Severity.CRITICAL
    assert high.severity == Severity.CRITICAL
    assert low.debate_resolution is not None and "same underlying issue" in low.debate_resolution

    messages = ctx.message_bus.history(ctx.review_id)
    assert len(messages) == 2  # each side sent one CRITIQUE to the other


async def test_debate_leaves_different_category_findings_unchanged(ctx):
    security_finding = _finding(severity=Severity.CRITICAL, category="security", detecting_agent="security_agent")
    perf_finding = _finding(
        id=new_id("F"), severity=Severity.LOW, category="performance", detecting_agent="performance_agent"
    )
    for f in (security_finding, perf_finding):
        await ctx.finding_store.add(f)

    result = await DebateAgent().run(
        ctx, [security_finding, perf_finding], conflict_clusters=[[security_finding.id, perf_finding.id]]
    )

    assert result.condition_context["independent_count"] == 1
    assert result.condition_context["resolved_count"] == 0
    assert security_finding.severity == Severity.CRITICAL  # untouched
    assert perf_finding.severity == Severity.LOW  # untouched
    assert "independent" in (security_finding.debate_resolution or "")


async def test_debate_avoids_llm_call_with_no_conflicts(ctx):
    result = await DebateAgent().run(ctx, findings=[], conflict_clusters=[])

    assert result.llm_calls_made == 0
    assert result.llm_calls_avoided == 1
