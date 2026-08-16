from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from backend.core.schemas.impact import ImpactAnalysisResult
from backend.integrations.chaos import ChaosState
from backend.integrations.tracing.noop_client import NoOpTracingClient

if TYPE_CHECKING:
    from backend.core.caching.tool_result_cache import ToolResultCache
    from backend.core.communication.message_bus import MessageBus
    from backend.core.events.event_bus import EventBus
    from backend.core.evidence.evidence_store import EvidenceStore
    from backend.core.findings.finding_store import FindingStore
    from backend.core.persistence.repositories import TokenUsageRepository
    from backend.integrations.github.client_protocol import GitHubClient
    from backend.integrations.github.schemas import PRFile, PullRequestPayload
    from backend.integrations.jira.client_protocol import JiraClient
    from backend.integrations.tracing.client_protocol import TracingClient
    from backend.llm.base.provider import LLMProvider
    from backend.llm.routing.token_budget import TokenBudget
    from backend.tools.base import Tool


@dataclass
class AgentContext:
    """Everything a single agent invocation needs. Holds live service handles
    (event bus, evidence store, LLM/github clients) plus the diff-first slice
    of PR data - never the whole repository (spec §41)."""

    review_id: str
    pr: PullRequestPayload
    diff_files: list[PRFile]
    impact: ImpactAnalysisResult
    evidence_store: EvidenceStore
    finding_store: FindingStore
    token_usage_repository: TokenUsageRepository
    event_bus: EventBus
    message_bus: MessageBus
    github_client: GitHubClient
    jira_client: JiraClient
    llm: LLMProvider
    token_budget: TokenBudget
    tools: list[Tool] = field(default_factory=list)
    # Defaults to a genuine no-op (not a mock) so callers that don't care about
    # tracing - e.g. existing tests - don't need to wire it up explicitly.
    tracing: TracingClient = field(default_factory=NoOpTracingClient)
    trace: Any = None
    # Optional: absent (None) means "no caching" rather than defaulting to a
    # real cache, since a cache needs a DB-backed repository to be useful -
    # unlike tracing, there's no meaningful no-op cache to fall back to.
    tool_cache: ToolResultCache | None = None
    # Defaults to a fresh, always-disabled state per context (mirrors the
    # tracing default) - the shared, API-toggleable instance is wired in
    # explicitly by review_runner.py via AppServices.chaos_state.
    chaos: ChaosState = field(default_factory=ChaosState)
