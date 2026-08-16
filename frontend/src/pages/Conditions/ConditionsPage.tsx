import { useMemo, useState } from "react";

import { Badge } from "../../components/common/Badge";
import { ConditionInspectorPanel } from "../../components/ConditionInspector/ConditionInspectorPanel";
import { useReviewStore } from "../../store/reviewStore";
import type { EdgeVisualState } from "../../store/reviewStore";

const STATE_TONE: Record<EdgeVisualState, "ok" | "danger" | "muted" | "info"> = {
  idle: "muted",
  active: "info",
  passed: "ok",
  failed: "danger",
  skipped: "muted",
};

export function ConditionsPage() {
  const edges = useReviewStore((s) => s.edges);
  const [selected, setSelected] = useState<string | null>(null);

  const rows = useMemo(
    () => Object.values(edges).sort((a, b) => a.def.priority - b.def.priority || a.def.source_agent.localeCompare(b.def.source_agent)),
    [edges],
  );

  return (
    <div className="grid h-[calc(100vh-140px)] grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
      <div className="glass-panel overflow-y-auto p-4">
        <div className="mb-3 flex items-baseline justify-between">
          <h3 className="mono-label">Conditional Edges</h3>
          <span className="text-[11px] text-mission-muted">{rows.length} edge(s)</span>
        </div>
        <div className="space-y-1.5">
          {rows.map((edge) => (
            <button
              key={edge.def.edge_id}
              onClick={() => setSelected(edge.def.edge_id)}
              className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left text-xs transition-colors ${
                selected === edge.def.edge_id
                  ? "border-mission-accent bg-mission-accent/5"
                  : "border-mission-border hover:bg-mission-panel/60"
              }`}
            >
              <span className="w-40 shrink-0 truncate text-slate-200">{edge.def.source_agent}</span>
              <span className="text-mission-muted">→</span>
              <span className="w-40 shrink-0 truncate text-slate-200">{edge.def.target_agent}</span>
              <code className="min-w-0 flex-1 truncate text-mission-accent">{edge.def.condition}</code>
              <Badge tone="info">{edge.def.condition_type}</Badge>
              <Badge tone={STATE_TONE[edge.state]}>{edge.state}</Badge>
            </button>
          ))}
          {rows.length === 0 && <p className="text-xs text-mission-muted">No graph topology loaded yet.</p>}
        </div>
      </div>
      <div className="overflow-y-auto">
        <ConditionInspectorPanel edgeId={selected} />
      </div>
    </div>
  );
}
