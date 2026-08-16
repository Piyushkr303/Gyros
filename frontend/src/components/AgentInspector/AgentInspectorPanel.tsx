import { liveStoreHooks, type ReducerStoreHooks } from "../../store/storeHooks";
import { GlassPanel } from "../common/GlassPanel";
import { Badge } from "../common/Badge";

interface Props {
  agentId: string | null;
  hooks?: ReducerStoreHooks;
}

export function AgentInspectorPanel({ agentId, hooks = liveStoreHooks }: Props) {
  const agents = hooks.useAgents();
  const toolCalls = hooks.useToolCalls();
  const agent = agentId ? agents[agentId] : undefined;
  const agentToolCalls = agentId ? toolCalls.filter((t) => t.agent === agentId) : [];

  if (!agentId || !agent) {
    return (
      <GlassPanel title="Agent Inspector">
        <p className="text-xs text-mission-muted">Click a node in the graph to inspect its execution.</p>
      </GlassPanel>
    );
  }

  return (
    <GlassPanel title="Agent Inspector" subtitle={agentId}>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs text-mission-muted">Status</span>
          <Badge tone={agent.status === "FAILED" ? "danger" : agent.status === "COMPLETED" ? "ok" : "info"}>
            {agent.status}
          </Badge>
        </div>

        {agent.durationMs !== undefined && (
          <div className="flex items-center justify-between text-xs">
            <span className="text-mission-muted">Latency</span>
            <span>{(agent.durationMs / 1000).toFixed(2)}s</span>
          </div>
        )}

        <div className="flex items-center justify-between text-xs">
          <span className="text-mission-muted">Findings</span>
          <span>{agent.findingsCount}</span>
        </div>

        {agent.dynamicallyActivated && (
          <div className="rounded border border-mission-warn/30 bg-mission-warn/5 p-2 text-xs text-mission-warn">
            ⚡ Dynamically activated{agent.activationReason ? `: ${agent.activationReason}` : ""}
          </div>
        )}

        {agent.skippedReason && (
          <div className="rounded border border-mission-border bg-mission-bg/60 p-2 text-xs text-mission-muted">
            Skipped: {agent.skippedReason}
          </div>
        )}

        {agent.error && (
          <div className="rounded border border-mission-danger/30 bg-mission-danger/5 p-2 text-xs text-mission-danger">
            {agent.error}
          </div>
        )}

        {agent.lastSummary && (
          <div className="space-y-1.5 border-t border-mission-border pt-2">
            <div className="mono-label">Execution Summary</div>
            {(
              [
                ["Objective", agent.lastSummary.objective],
                ["Decision", agent.lastSummary.decision],
                ["Action", agent.lastSummary.action],
                ["Tool", agent.lastSummary.tool ?? "—"],
                ["Observation", agent.lastSummary.observation],
                ["Next Action", agent.lastSummary.next_action],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="text-xs">
                <div className="text-[10px] uppercase tracking-wide text-mission-muted">{label}</div>
                <div className="text-slate-200">{value}</div>
              </div>
            ))}
          </div>
        )}

        {agentToolCalls.length > 0 && (
          <div className="space-y-1 border-t border-mission-border pt-2">
            <div className="mono-label">Tool Calls</div>
            {agentToolCalls.map((t, i) => (
              <div key={i} className="flex items-center justify-between text-xs">
                <span className="text-slate-300">{t.tool}</span>
                <Badge tone={t.status === "success" ? "ok" : t.status === "failed" ? "danger" : "info"}>
                  {t.status}
                </Badge>
              </div>
            ))}
          </div>
        )}
      </div>
    </GlassPanel>
  );
}
