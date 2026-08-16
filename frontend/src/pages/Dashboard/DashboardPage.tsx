import { useMemo } from "react";

import { CommunicationFeed } from "../../components/CommunicationGraph/CommunicationFeed";
import { StatTile } from "../../components/common/StatTile";
import { Timeline } from "../../components/Timeline/Timeline";
import { ToolMonitor } from "../../components/ToolMonitor/ToolMonitor";
import { useReviewStore } from "../../store/reviewStore";

const ACTIVE_STATUSES = new Set(["RUNNING", "CALLING_TOOL", "THINKING_SUMMARY", "COMMUNICATING", "VALIDATING"]);

export function DashboardPage() {
  const agents = useReviewStore((s) => s.agents);
  const toolCalls = useReviewStore((s) => s.toolCalls);
  const findings = useReviewStore((s) => s.findings);
  const tokenRecords = useReviewStore((s) => s.tokenRecords);
  const reviewStatus = useReviewStore((s) => s.reviewStatus);
  const reviewId = useReviewStore((s) => s.reviewId);
  const mockBanner = useReviewStore((s) => s.mockBanner);

  const stats = useMemo(() => {
    const findingList = Object.values(findings);
    const agentsActive = Object.values(agents).filter((a) => ACTIVE_STATUSES.has(a.status)).length;
    const toolsRunning = toolCalls.filter((t) => t.status === "running").length;
    const validated = findingList.filter((f) => f.validator_status === "CONFIRMED").length;
    const critical = findingList.filter((f) => f.severity === "HIGH" || f.severity === "CRITICAL").length;
    const totalTokens = tokenRecords.reduce((sum, r) => sum + r.input_tokens + r.output_tokens, 0);
    const avoided = tokenRecords.filter((r) => r.llm_call_avoided).length;
    const savingsPct = tokenRecords.length > 0 ? Math.round((avoided / tokenRecords.length) * 100) : 0;
    const accepted = findingList.filter((f) => f.critic_status === "ACCEPTED").length;

    return {
      agentsActive,
      toolsRunning,
      findingsCount: findingList.length,
      validated,
      critical,
      totalTokens,
      savingsPct,
      accepted,
    };
  }, [agents, toolCalls, findings, tokenRecords]);

  return (
    <div className="space-y-4">
      {(mockBanner.groq || mockBanner.github) && (
        <div className="glass-panel border-mission-warn/40 bg-mission-warn/5 px-4 py-2 text-xs text-mission-warn">
          MOCK MODE — {mockBanner.groq && "Groq LLM calls are simulated from real deterministic evidence. "}
          {mockBanner.github && "GitHub posting is simulated (logged, not sent to a real repository)."}
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-lg font-semibold text-slate-100">
            {reviewId ? `Review ${reviewId}` : "No active review"}
          </h2>
          <p className="text-xs text-mission-muted">Status: {reviewStatus ?? "in progress"}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Agents Active" value={stats.agentsActive} accent="accent" />
        <StatTile label="Tools Running" value={stats.toolsRunning} accent="accent" />
        <StatTile label="Findings" value={stats.findingsCount} />
        <StatTile label="Validated" value={stats.validated} accent="ok" />
        <StatTile label="Critical" value={stats.critical} accent="danger" />
        <StatTile label="Token Usage" value={stats.totalTokens} />
        <StatTile label="LLM Calls Avoided" value={`${stats.savingsPct}%`} accent="ok" />
        <StatTile label="Findings Confirmed / Total" value={`${stats.accepted} / ${stats.findingsCount}`} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Timeline />
        <ToolMonitor />
        <CommunicationFeed />
      </div>
    </div>
  );
}
