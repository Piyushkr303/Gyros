import asyncio
from pathlib import Path

import pytest

from backend.core.agents.agent_context import AgentContext
from backend.core.communication.message_bus import MessageBus
from backend.core.evidence.evidence_store import EvidenceStore
from backend.core.events.event_bus import EventBus
from backend.core.findings.finding_store import FindingStore
from backend.core.graph.engine import GraphEngine
from backend.core.graph.graph_config import load_graph_definition
from backend.core.orchestration.human_approval import ApprovalAction, ApprovalDecision, HumanApprovalGate
from backend.core.persistence.db import dispose_db, get_session_factory, init_db
from backend.core.persistence.repositories import (
    AgentMessageRepository,
    EventRepository,
    EvidenceRepository,
    FindingRepository,
    ReviewRepository,
    TokenUsageRepository,
)
from backend.core.schemas.finding import ValidationStatus
from backend.core.schemas.impact import ImpactAnalysisResult
from backend.core.schemas.review import ReviewSession, ReviewStatus
from backend.core.utils import new_id, now_iso
from backend.integrations.github.mock_client import MockGitHubClient
from backend.integrations.jira.mock_client import MockJiraClient
from backend.llm.groq.mock_provider import MockGroqProvider
from backend.llm.routing.token_budget import TokenBudget

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "demo_pr"
CONFIGS_DIR = REPO_ROOT / "configs"


@pytest.fixture
async def wired(tmp_path):
    db_path = tmp_path / "test.db"
    await init_db(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    session_factory = get_session_factory()

    event_bus = EventBus(EventRepository(session_factory))
    evidence_store = EvidenceStore(EvidenceRepository(session_factory))
    finding_store = FindingStore(FindingRepository(session_factory))
    message_bus = MessageBus(event_bus, AgentMessageRepository(session_factory))
    human_approval_gate = HumanApprovalGate()
    review_repo = ReviewRepository(session_factory)
    token_repo = TokenUsageRepository(session_factory)

    github_client = MockGitHubClient(FIXTURES_DIR)
    jira_client = MockJiraClient(FIXTURES_DIR)
    llm = MockGroqProvider()
    graph_definition = load_graph_definition(CONFIGS_DIR / "graph.yaml")
    engine = GraphEngine(graph_definition, event_bus, message_bus, human_approval_gate, review_repo)

    yield {
        "event_bus": event_bus,
        "evidence_store": evidence_store,
        "finding_store": finding_store,
        "message_bus": message_bus,
        "human_approval_gate": human_approval_gate,
        "review_repo": review_repo,
        "token_repo": token_repo,
        "github_client": github_client,
        "jira_client": jira_client,
        "llm": llm,
        "engine": engine,
    }
    await dispose_db()


async def test_full_review_confirms_missing_auth_finding(wired):
    github_client = wired["github_client"]
    pr = await github_client.get_pull_request("demo-org/demo-payments", 238)

    session = ReviewSession(
        review_id=new_id("rev"),
        pr_number=pr.number,
        repo=pr.repo,
        pr_title=pr.title,
        head_sha=pr.head_sha,
        base_sha=pr.base_sha,
        status=ReviewStatus.RECEIVED,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    await wired["review_repo"].add(session)

    ctx = AgentContext(
        review_id=session.review_id,
        pr=pr,
        diff_files=pr.files,
        impact=ImpactAnalysisResult(),
        evidence_store=wired["evidence_store"],
        finding_store=wired["finding_store"],
        token_usage_repository=wired["token_repo"],
        event_bus=wired["event_bus"],
        message_bus=wired["message_bus"],
        github_client=github_client,
        jira_client=wired["jira_client"],
        llm=wired["llm"],
        token_budget=TokenBudget(),
    )

    engine = wired["engine"]
    run_task = asyncio.create_task(engine.run(ctx, session))

    for _ in range(500):
        if wired["human_approval_gate"].is_pending(session.review_id):
            break
        await asyncio.sleep(0.02)
    else:
        run_task.cancel()
        pytest.fail("Review never reached human approval")

    wired["human_approval_gate"].resolve(session.review_id, ApprovalDecision(action=ApprovalAction.APPROVE))
    result_session = await asyncio.wait_for(run_task, timeout=15)

    assert result_session.status == ReviewStatus.PUBLISHED

    findings = await wired["finding_store"].list_by_review(session.review_id)
    assert findings, "Expected at least one finding for the missing-authorization-check demo PR"

    security_findings = [f for f in findings if f.detecting_agent == "security_agent"]
    assert security_findings, "Security agent should have found the missing authorization check"
    assert any(f.validator_status == ValidationStatus.CONFIRMED for f in security_findings)


async def test_impact_analysis_flags_security_sensitive(wired):
    github_client = wired["github_client"]
    pr = await github_client.get_pull_request("demo-org/demo-payments", 238)
    assert any("payment" in f.filename for f in pr.files)
    assert pr.files[0].patch  # a real unidiff-parseable patch was computed
