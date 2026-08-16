from __future__ import annotations

from dataclasses import dataclass

from backend.config.settings import Settings
from backend.core.caching.tool_result_cache import ToolResultCache
from backend.core.communication.message_bus import MessageBus
from backend.core.events.event_bus import EventBus
from backend.core.evidence.evidence_store import EvidenceStore
from backend.core.findings.finding_store import FindingStore
from backend.core.graph.engine import GraphEngine
from backend.core.graph.graph_config import GraphDefinition
from backend.core.orchestration.human_approval import HumanApprovalGate
from backend.core.persistence.repositories import ReviewRepository, TokenUsageRepository
from backend.integrations.chaos import ChaosState
from backend.integrations.github.client_protocol import GitHubClient
from backend.integrations.jira.client_protocol import JiraClient
from backend.integrations.tracing.composite_client import CompositeTracingClient
from backend.llm.base.provider import LLMProvider
from backend.llm.routing.token_budget import TokenBudget


@dataclass
class AppServices:
    """Every singleton wired up once at startup (backend/api/main.py) and
    shared across requests/background tasks."""

    settings: Settings
    event_bus: EventBus
    evidence_store: EvidenceStore
    finding_store: FindingStore
    message_bus: MessageBus
    human_approval_gate: HumanApprovalGate
    review_repository: ReviewRepository
    token_usage_repository: TokenUsageRepository
    github_client: GitHubClient
    jira_client: JiraClient
    tracing: CompositeTracingClient
    tool_cache: ToolResultCache
    chaos_state: ChaosState
    llm_provider: LLMProvider
    token_budget: TokenBudget
    graph_definition: GraphDefinition
    graph_engine: GraphEngine
