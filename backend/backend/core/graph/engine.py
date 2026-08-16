from __future__ import annotations

import asyncio
import logging

from backend.agents.accessibility.accessibility_agent import AccessibilityAgent
from backend.agents.api_contract.api_contract_agent import ApiContractAgent
from backend.agents.architecture.architecture_agent import ArchitectureAgent
from backend.agents.bug_detection.bug_detection_agent import BugDetectionAgent
from backend.agents.ci_investigator.ci_investigator_agent import CIInvestigatorAgent
from backend.agents.code_impact.code_impact_agent import CodeImpactAgent
from backend.agents.conflict_resolver.conflict_resolver_agent import ConflictResolverAgent
from backend.agents.critic.critic_agent import CriticAgent
from backend.agents.database.database_agent import DatabaseAgent
from backend.agents.debate.debate_agent import DebateAgent
from backend.agents.dependency.dependency_agent import DependencyAgent
from backend.agents.documentation.documentation_agent import DocumentationAgent
from backend.agents.final_review.final_review_agent import FinalReviewAgent
from backend.agents.impact_analyzer.impact_analyzer_agent import ImpactAnalyzerAgent
from backend.agents.observability.observability_agent import ObservabilityAgent
from backend.agents.orchestrator.orchestrator_agent import OrchestratorAgent
from backend.agents.performance.performance_agent import PerformanceAgent
from backend.agents.reliability.reliability_agent import ReliabilityAgent
from backend.agents.requirement.requirement_agent import RequirementAgent
from backend.agents.security.security_agent import SecurityAgent
from backend.agents.static_analysis.static_analysis_agent import StaticAnalysisAgent
from backend.agents.test.test_agent import TestAgent
from backend.agents.validator.validator_agent import ValidatorAgent
from backend.core.agents.agent_context import AgentContext
from backend.core.agents.agent_result import AgentResult
from backend.core.communication.message_bus import MessageBus
from backend.core.conditions.evaluator import evaluate_edge
from backend.core.events.event_bus import EventBus
from backend.core.graph.graph_config import GraphDefinition
from backend.core.orchestration.github_publisher import publish_review
from backend.core.orchestration.graph_context import GraphContext
from backend.core.orchestration.human_approval import ApprovalAction, HumanApprovalGate
from backend.core.orchestration.jira_publisher import publish_jira_update
from backend.core.persistence.repositories import ReviewRepository
from backend.core.schemas.agent_state import AgentStatus
from backend.core.schemas.edge import ConditionalEdge
from backend.core.schemas.events import EventType
from backend.core.schemas.finding import CriticStatus, Finding, Severity, ValidationStatus
from backend.core.schemas.impact import ImpactAnalysisResult
from backend.core.schemas.message import MessageType
from backend.core.schemas.review import ReviewSession, ReviewStatus
from backend.core.utils import now_iso

logger = logging.getLogger(__name__)

_MAX_REANALYSIS_RETRIES = 1
_PARALLEL_AGENT_NAMES = (
    "security_agent",
    "bug_detection_agent",
    "test_agent",
    "performance_agent",
    "documentation_agent",
    "dependency_agent",
    "reliability_agent",
    "api_contract_agent",
    "database_agent",
    "observability_agent",
    "architecture_agent",
    "code_impact_agent",
    "static_analysis_agent",
    "accessibility_agent",
    "requirement_agent",
)
_HIGH_SEVERITY = (Severity.HIGH, Severity.CRITICAL)


class GraphEngine:
    """Runs one review through the conditional agent graph defined in
    configs/graph.yaml (spec §6-11, §56-58). Edge conditions are always
    evaluated deterministically (backend.core.conditions.evaluator);
    parallel-eligible agents are dispatched with asyncio.gather; the
    reanalysis and critic re-investigation loops are bounded so the graph
    always terminates."""

    def __init__(
        self,
        graph_definition: GraphDefinition,
        event_bus: EventBus,
        message_bus: MessageBus,
        human_approval_gate: HumanApprovalGate,
        review_repository: ReviewRepository,
    ) -> None:
        self.graph_definition = graph_definition
        self.event_bus = event_bus
        self.message_bus = message_bus
        self.human_approval_gate = human_approval_gate
        self.review_repository = review_repository

        self.orchestrator = OrchestratorAgent()
        self.impact_analyzer = ImpactAnalyzerAgent()
        self.security_agent = SecurityAgent()
        self.bug_detection_agent = BugDetectionAgent()
        self.test_agent = TestAgent()
        self.performance_agent = PerformanceAgent()
        self.documentation_agent = DocumentationAgent()
        self.dependency_agent = DependencyAgent()
        self.reliability_agent = ReliabilityAgent()
        self.api_contract_agent = ApiContractAgent()
        self.database_agent = DatabaseAgent()
        self.observability_agent = ObservabilityAgent()
        self.architecture_agent = ArchitectureAgent()
        self.code_impact_agent = CodeImpactAgent()
        self.static_analysis_agent = StaticAnalysisAgent()
        self.accessibility_agent = AccessibilityAgent()
        self.ci_investigator_agent = CIInvestigatorAgent()
        self.requirement_agent = RequirementAgent()
        self.validator = ValidatorAgent()
        self.critic = CriticAgent()
        self.conflict_resolver = ConflictResolverAgent()
        self.debate_agent = DebateAgent()
        self.final_review = FinalReviewAgent()

        self._parallel_agents = {
            "security_agent": self.security_agent,
            "bug_detection_agent": self.bug_detection_agent,
            "test_agent": self.test_agent,
            "performance_agent": self.performance_agent,
            "documentation_agent": self.documentation_agent,
            "dependency_agent": self.dependency_agent,
            "reliability_agent": self.reliability_agent,
            "api_contract_agent": self.api_contract_agent,
            "database_agent": self.database_agent,
            "observability_agent": self.observability_agent,
            "architecture_agent": self.architecture_agent,
            "code_impact_agent": self.code_impact_agent,
            "static_analysis_agent": self.static_analysis_agent,
            "accessibility_agent": self.accessibility_agent,
            "requirement_agent": self.requirement_agent,
        }
        # NOT in _parallel_agents / _PARALLEL_AGENT_NAMES: ci_investigator_agent is
        # dynamically activated (see _run_dynamic_activation), not part of the
        # up-front wave-1 fan-out.

    async def run(self, ctx: AgentContext, session: ReviewSession) -> ReviewSession:
        review_id = session.review_id
        graph_context = GraphContext(review_id=review_id)

        await self.event_bus.publish(review_id, EventType.PLANNING_STARTED, {})

        orch_result = await self.orchestrator.run(ctx)
        graph_context.record_agent_result("orchestrator", orch_result)

        impact_result = await self.impact_analyzer.run(ctx)
        graph_context.record_agent_result("impact_analyzer", impact_result)
        impact = ImpactAnalysisResult(**impact_result.condition_context)
        graph_context.impact = impact
        ctx.impact = impact

        to_run = await self._evaluate_fanout_edges(graph_context, review_id)

        tasks = {
            name: agent.run(ctx) for name, agent in self._parallel_agents.items() if name in to_run
        }
        if tasks:
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for name, result in zip(tasks.keys(), results, strict=True):
                if isinstance(result, BaseException):
                    logger.exception("Parallel agent %s raised unexpectedly", name, exc_info=result)
                    continue
                graph_context.record_agent_result(name, result)

        await self._evaluate_validator_fanin_edges(graph_context, review_id, to_run)

        all_findings: list[Finding] = []
        for name in _PARALLEL_AGENT_NAMES:
            result = graph_context.agent_results.get(name)
            if result:
                all_findings.extend(result.findings)

        validator_result = await self.validator.run(ctx, all_findings)
        graph_context.record_agent_result("validator_agent", validator_result)

        await self._run_reanalysis_loop(ctx, graph_context, all_findings, review_id)

        await self._run_dynamic_activation(ctx, graph_context, all_findings, review_id)

        critic_result = await self.critic.run(ctx, all_findings)
        graph_context.record_agent_result("critic_agent", critic_result)

        await self._run_critic_loop(ctx, graph_context, all_findings, review_id)
        self._sync_validator_critic_tallies(graph_context, all_findings)

        conflict_result = await self.conflict_resolver.run(ctx, all_findings)
        graph_context.record_agent_result("conflict_resolver_agent", conflict_result)

        conflict_clusters = conflict_result.condition_context.get("conflict_clusters", [])
        debate_result = await self.debate_agent.run(ctx, all_findings, conflict_clusters)
        graph_context.record_agent_result("debate_agent", debate_result)

        final_result = await self.final_review.run(ctx, all_findings)
        graph_context.record_agent_result("final_review_agent", final_result)

        session.status = ReviewStatus.AWAITING_APPROVAL
        session.updated_at = now_iso()
        await self.review_repository.update(session)
        await self.event_bus.publish(
            review_id,
            EventType.APPROVAL_REQUIRED,
            {"publishable_count": len(final_result.findings)},
        )

        self.human_approval_gate.open(review_id)
        decision = await self.human_approval_gate.wait_for_decision(review_id)
        await self.event_bus.publish(
            review_id, EventType.APPROVAL_DECIDED, {"action": decision.action.value}
        )

        graph_context.agent_results["human_approval"] = AgentResult(
            agent_name="human_approval",
            status=AgentStatus.COMPLETED,
            condition_context={"decision": decision.action.value},
        )

        publish_edges = self.graph_definition.edges_from("human_approval")
        condition_ctx = graph_context.as_condition_dict()
        for edge in publish_edges:
            eval_result = evaluate_edge(edge, condition_ctx, review_id, all_edges=publish_edges)
            await self._emit_edge_event(review_id, edge, eval_result)
            if eval_result.passed and decision.action == ApprovalAction.APPROVE:
                await publish_review(
                    session, final_result.findings, ctx.github_client, self.event_bus
                )
                session.status = ReviewStatus.PUBLISHED

        if decision.action == ApprovalAction.REJECT:
            session.status = ReviewStatus.REJECTED

        if decision.action in (ApprovalAction.APPROVE, ApprovalAction.REJECT):
            requirement_result = graph_context.agent_results.get("requirement_agent")
            issue_key = (
                requirement_result.condition_context.get("issue_key")
                if requirement_result
                else None
            )
            if issue_key:
                await publish_jira_update(
                    session,
                    final_result.findings,
                    issue_key,
                    approved=decision.action == ApprovalAction.APPROVE,
                    jira_client=ctx.jira_client,
                    event_bus=self.event_bus,
                )

        session.updated_at = now_iso()
        await self.review_repository.update(session)
        await self.event_bus.publish(
            review_id, EventType.REVIEW_COMPLETED, {"status": session.status.value}
        )
        return session

    # --- edge orchestration helpers ------------------------------------
    async def _evaluate_fanout_edges(self, graph_context: GraphContext, review_id: str) -> set[str]:
        edges = self.graph_definition.edges_from("impact_analyzer")
        condition_ctx = graph_context.as_condition_dict()
        to_run: set[str] = set()
        for edge in edges:
            eval_result = evaluate_edge(edge, condition_ctx, review_id, all_edges=edges)
            await self._emit_edge_event(review_id, edge, eval_result)
            if eval_result.passed:
                to_run.add(edge.target_agent)
            else:
                await self.event_bus.publish(
                    review_id,
                    EventType.AGENT_SKIPPED,
                    {"agent": edge.target_agent, "reason": eval_result.reason},
                )
        return to_run

    async def _evaluate_validator_fanin_edges(
        self, graph_context: GraphContext, review_id: str, to_run: set[str]
    ) -> None:
        for source_name in _PARALLEL_AGENT_NAMES:
            if source_name not in to_run:
                continue
            edges = self.graph_definition.edges_from(source_name)
            condition_ctx = graph_context.as_condition_dict()
            for edge in edges:
                eval_result = evaluate_edge(edge, condition_ctx, review_id, all_edges=edges)
                await self._emit_edge_event(review_id, edge, eval_result)

    async def _run_reanalysis_loop(
        self,
        ctx: AgentContext,
        graph_context: GraphContext,
        all_findings: list[Finding],
        review_id: str,
    ) -> None:
        edges = self.graph_definition.edges_from("validator_agent")
        reanalysis_edge = next((e for e in edges if e.target_agent == "validator_agent"), None)
        if reanalysis_edge is None:
            return

        condition_ctx = graph_context.as_condition_dict()
        eval_result = evaluate_edge(reanalysis_edge, condition_ctx, review_id, all_edges=edges)
        await self._emit_edge_event(review_id, reanalysis_edge, eval_result)
        if not eval_result.passed:
            return

        eligible = [
            f
            for f in all_findings
            if f.validator_status == ValidationStatus.UNCERTAIN
            and graph_context.reanalysis_counts.get(f"validator:{f.id}", 0)
            < _MAX_REANALYSIS_RETRIES
        ]
        if not eligible:
            return

        for f in eligible:
            graph_context.reanalysis_counts[f"validator:{f.id}"] = _MAX_REANALYSIS_RETRIES
        await self.event_bus.publish(
            review_id,
            EventType.REPLAN_STARTED,
            {"reason": "uncertain findings", "finding_ids": [f.id for f in eligible]},
        )
        for f in eligible:
            await self.message_bus.send(
                review_id=review_id,
                sender="validator_agent",
                receiver=f.detecting_agent,
                type=MessageType.REQUEST_EVIDENCE,
                summary=f"Requesting additional evidence for finding {f.id} ({f.title})",
                finding_id=f.id,
            )
        retry_result = await self.validator.run(ctx, eligible)
        graph_context.record_agent_result("validator_agent", retry_result)
        await self.event_bus.publish(
            review_id, EventType.REPLAN_COMPLETED, {"finding_ids": [f.id for f in eligible]}
        )

    async def _run_dynamic_activation(
        self,
        ctx: AgentContext,
        graph_context: GraphContext,
        all_findings: list[Finding],
        review_id: str,
    ) -> None:
        """Dynamic agent activation (spec: orchestrator spawning an agent
        mid-run based on a discovery, not a pre-planned static path). If
        wave-1 confirmed a HIGH/CRITICAL finding, emit a real event and let
        the EVENT-type edge validator_agent -> ci_investigator_agent decide
        whether to activate it - CI Investigator is never part of the
        up-front fan-out (see __init__)."""
        high_severity_confirmed = [
            f
            for f in all_findings
            if f.validator_status == ValidationStatus.CONFIRMED and f.severity in _HIGH_SEVERITY
        ]
        if high_severity_confirmed:
            await self.event_bus.publish(
                review_id,
                EventType.HIGH_SEVERITY_FINDING_CONFIRMED,
                {
                    "finding_ids": [f.id for f in high_severity_confirmed],
                    "count": len(high_severity_confirmed),
                },
            )
            graph_context.last_event = {"type": EventType.HIGH_SEVERITY_FINDING_CONFIRMED.value}

        edges = self.graph_definition.edges_from("validator_agent")
        dynamic_edge = next((e for e in edges if e.target_agent == "ci_investigator_agent"), None)
        if dynamic_edge is None:
            return

        condition_ctx = graph_context.as_condition_dict()
        eval_result = evaluate_edge(dynamic_edge, condition_ctx, review_id, all_edges=edges)
        await self._emit_edge_event(review_id, dynamic_edge, eval_result)
        if not eval_result.passed:
            return

        await self.event_bus.publish(
            review_id,
            EventType.AGENT_DYNAMICALLY_ACTIVATED,
            {
                "agent": "ci_investigator_agent",
                "reason": f"{len(high_severity_confirmed)} HIGH/CRITICAL-severity finding(s) confirmed in wave 1",
            },
        )
        ci_result = await self.ci_investigator_agent.run(ctx)
        graph_context.record_agent_result("ci_investigator_agent", ci_result)
        all_findings.extend(ci_result.findings)

        if ci_result.findings:
            retry_result = await self.validator.run(ctx, ci_result.findings)
            graph_context.record_agent_result("validator_agent", retry_result)

    async def _run_critic_loop(
        self,
        ctx: AgentContext,
        graph_context: GraphContext,
        all_findings: list[Finding],
        review_id: str,
    ) -> None:
        edges = self.graph_definition.edges_from("critic_agent")
        loop_edge = next((e for e in edges if e.target_agent == "validator_agent"), None)
        if loop_edge is None:
            return

        condition_ctx = graph_context.as_condition_dict()
        eval_result = evaluate_edge(loop_edge, condition_ctx, review_id, all_edges=edges)
        await self._emit_edge_event(review_id, loop_edge, eval_result)
        if not eval_result.passed:
            return

        weak = [
            f
            for f in all_findings
            if f.critic_status == CriticStatus.WEAK_EVIDENCE
            and graph_context.reanalysis_counts.get(f"critic:{f.id}", 0) < _MAX_REANALYSIS_RETRIES
        ]
        if not weak:
            return

        for f in weak:
            graph_context.reanalysis_counts[f"critic:{f.id}"] = _MAX_REANALYSIS_RETRIES
        await self.event_bus.publish(
            review_id,
            EventType.REPLAN_STARTED,
            {"reason": "weak-evidence findings", "finding_ids": [f.id for f in weak]},
        )
        for f in weak:
            await self.message_bus.send(
                review_id=review_id,
                sender="critic_agent",
                receiver=f.detecting_agent,
                type=MessageType.REQUEST_EVIDENCE,
                summary=f"Critic flagged weak evidence for finding {f.id}; requesting reinforcement",
                finding_id=f.id,
            )
        retry_result = await self.critic.run(ctx, weak)
        graph_context.record_agent_result("critic_agent", retry_result)
        await self.event_bus.publish(
            review_id, EventType.REPLAN_COMPLETED, {"finding_ids": [f.id for f in weak]}
        )

    def _sync_validator_critic_tallies(
        self, graph_context: GraphContext, all_findings: list[Finding]
    ) -> None:
        confirmed = sum(1 for f in all_findings if f.validator_status == ValidationStatus.CONFIRMED)
        rejected = sum(1 for f in all_findings if f.validator_status == ValidationStatus.REJECTED)
        uncertain = sum(1 for f in all_findings if f.validator_status == ValidationStatus.UNCERTAIN)
        graph_context.agent_results["validator_agent"] = AgentResult(
            agent_name="validator_agent",
            status=AgentStatus.COMPLETED,
            findings=all_findings,
            condition_context={
                "confirmed_count": confirmed,
                "rejected_count": rejected,
                "uncertain_count": uncertain,
            },
        )
        accepted = sum(1 for f in all_findings if f.critic_status == CriticStatus.ACCEPTED)
        weak = sum(1 for f in all_findings if f.critic_status == CriticStatus.WEAK_EVIDENCE)
        duplicate = sum(1 for f in all_findings if f.critic_status == CriticStatus.DUPLICATE)
        graph_context.agent_results["critic_agent"] = AgentResult(
            agent_name="critic_agent",
            status=AgentStatus.COMPLETED,
            findings=all_findings,
            condition_context={
                "accepted_count": accepted,
                "weak_evidence_count": weak,
                "duplicate_count": duplicate,
            },
        )

    async def _emit_edge_event(self, review_id: str, edge: ConditionalEdge, eval_result) -> None:
        await self.event_bus.publish(
            review_id,
            EventType.EDGE_EVALUATED,
            {"edge": edge.model_dump(), "result": eval_result.model_dump()},
        )
        if eval_result.passed:
            await self.event_bus.publish(
                review_id,
                EventType.EDGE_TRIGGERED,
                {"edge": edge.model_dump(), "result": eval_result.model_dump()},
            )
        else:
            await self.event_bus.publish(
                review_id,
                EventType.EDGE_SKIPPED,
                {"edge": edge.model_dump(), "result": eval_result.model_dump()},
            )
