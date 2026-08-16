from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import get_settings
from backend.core.caching.tool_result_cache import ToolResultCache
from backend.core.communication.message_bus import MessageBus
from backend.core.events.event_bus import EventBus
from backend.core.evidence.evidence_store import EvidenceStore
from backend.core.findings.finding_store import FindingStore
from backend.core.graph.engine import GraphEngine
from backend.core.graph.graph_config import load_graph_definition
from backend.core.orchestration.human_approval import HumanApprovalGate
from backend.core.orchestration.services import AppServices
from backend.core.persistence.db import dispose_db, get_session_factory, init_db
from backend.core.persistence.repositories import (
    AgentMessageRepository,
    EventRepository,
    EvidenceRepository,
    FindingRepository,
    ReviewRepository,
    TokenUsageRepository,
    ToolResultCacheRepository,
)
from backend.integrations.chaos import ChaosState
from backend.integrations.github.factory import build_github_client
from backend.integrations.jira.factory import build_jira_client
from backend.integrations.tracing.factory import build_tracing_client
from backend.llm.factory import build_llm_provider
from backend.llm.routing.token_budget import TokenBudget

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.getLogger().setLevel(settings.log_level)

    await init_db(settings.database_url)
    session_factory = get_session_factory()

    event_repo = EventRepository(session_factory)
    evidence_repo = EvidenceRepository(session_factory)
    finding_repo = FindingRepository(session_factory)
    message_repo = AgentMessageRepository(session_factory)
    token_repo = TokenUsageRepository(session_factory)
    review_repo = ReviewRepository(session_factory)
    tool_cache_repo = ToolResultCacheRepository(session_factory)

    event_bus = EventBus(event_repo)
    evidence_store = EvidenceStore(evidence_repo)
    finding_store = FindingStore(finding_repo)
    message_bus = MessageBus(event_bus, message_repo)
    human_approval_gate = HumanApprovalGate()
    tool_cache = ToolResultCache(tool_cache_repo)
    chaos_state = ChaosState()

    github_client = build_github_client(settings)
    jira_client = build_jira_client(settings)
    tracing = build_tracing_client(settings)
    llm_provider = build_llm_provider(settings)
    token_budget = TokenBudget()

    graph_definition = load_graph_definition(settings.configs_dir / "graph.yaml")
    graph_engine = GraphEngine(
        graph_definition, event_bus, message_bus, human_approval_gate, review_repo
    )

    logger.info(
        "Startup: groq_mode=%s github_mode=%s jira_mode=%s tracing_mode=%s",
        settings.groq_mode,
        settings.github_mode,
        settings.jira_mode,
        settings.tracing_mode,
    )

    app.state.services = AppServices(
        settings=settings,
        event_bus=event_bus,
        evidence_store=evidence_store,
        finding_store=finding_store,
        message_bus=message_bus,
        human_approval_gate=human_approval_gate,
        review_repository=review_repo,
        token_usage_repository=token_repo,
        github_client=github_client,
        jira_client=jira_client,
        tracing=tracing,
        tool_cache=tool_cache,
        chaos_state=chaos_state,
        llm_provider=llm_provider,
        token_budget=token_budget,
        graph_definition=graph_definition,
        graph_engine=graph_engine,
    )
    app.state.background_tasks = set()

    yield

    await dispose_db()


def create_app() -> FastAPI:
    app = FastAPI(title="Live Multi-Agent PR Reviewer", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from backend.api.routes import chaos, reviews, webhooks, websocket

    app.include_router(webhooks.router)
    app.include_router(reviews.router)
    app.include_router(websocket.router)
    app.include_router(chaos.router)

    @app.get("/health")
    async def health() -> dict:
        settings = get_settings()
        return {
            "status": "ok",
            "groq_mode": settings.groq_mode,
            "github_mode": settings.github_mode,
            "jira_mode": settings.jira_mode,
            "tracing_mode": settings.tracing_mode,
        }

    return app


app = create_app()
