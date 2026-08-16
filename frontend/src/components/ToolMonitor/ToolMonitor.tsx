import { useReviewStore } from "../../store/reviewStore";
import { GlassPanel } from "../common/GlassPanel";
import { Badge } from "../common/Badge";

export function ToolMonitor() {
  const toolCalls = useReviewStore((s) => s.toolCalls);

  return (
    <GlassPanel title="Tool Monitor" subtitle={`${toolCalls.length} call(s)`}>
      <div className="max-h-64 space-y-1 overflow-y-auto">
        {toolCalls.length === 0 && <p className="text-xs text-mission-muted">No tool calls yet.</p>}
        {[...toolCalls].reverse().map((t, i) => (
          <div key={i} className="flex items-center justify-between text-xs">
            <span className="text-slate-300">
              {t.agent} <span className="text-mission-muted">→</span> {t.tool}
            </span>
            <div className="flex items-center gap-2">
              {t.durationMs !== undefined && <span className="text-mission-muted">{t.durationMs}ms</span>}
              <Badge tone={t.status === "success" ? "ok" : t.status === "failed" ? "danger" : "info"}>
                {t.status}
              </Badge>
            </div>
          </div>
        ))}
      </div>
    </GlassPanel>
  );
}
