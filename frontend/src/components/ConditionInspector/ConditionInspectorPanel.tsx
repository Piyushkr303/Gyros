import { liveStoreHooks, type ReducerStoreHooks } from "../../store/storeHooks";
import { GlassPanel } from "../common/GlassPanel";
import { Badge } from "../common/Badge";

interface Props {
  edgeId: string | null;
  hooks?: ReducerStoreHooks;
}

export function ConditionInspectorPanel({ edgeId, hooks = liveStoreHooks }: Props) {
  const edges = hooks.useEdges();
  const edge = edgeId ? edges[edgeId] : undefined;

  if (!edgeId || !edge) {
    return (
      <GlassPanel title="Condition Inspector">
        <p className="text-xs text-mission-muted">Click an edge in the graph to inspect its condition.</p>
      </GlassPanel>
    );
  }

  const result = edge.lastResult;

  return (
    <GlassPanel title="Condition Inspector" subtitle={edge.def.condition_type}>
      <div className="space-y-2 text-xs">
        <div className="flex items-center justify-between">
          <span className="text-mission-muted">Source</span>
          <span className="text-slate-200">{edge.def.source_agent}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-mission-muted">Target</span>
          <span className="text-slate-200">{edge.def.target_agent}</span>
        </div>
        <div className="border-t border-mission-border pt-2">
          <div className="text-[10px] uppercase tracking-wide text-mission-muted">Condition</div>
          <code className="mt-1 block rounded bg-mission-bg/60 p-1.5 text-mission-accent">{edge.def.condition}</code>
        </div>

        {result ? (
          <>
            <div className="flex items-center justify-between">
              <span className="text-mission-muted">Current Value</span>
              <span className="text-slate-200">{JSON.stringify(result.value)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-mission-muted">Evaluation</span>
              <Badge tone={result.passed ? "ok" : "danger"}>{result.passed ? "TRUE ✓" : "FALSE ✗"}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-mission-muted">Evaluated At</span>
              <span className="text-slate-200">{new Date(result.evaluated_at).toLocaleTimeString()}</span>
            </div>
            <div className="border-t border-mission-border pt-2">
              <div className="text-[10px] uppercase tracking-wide text-mission-muted">Reason</div>
              <p className="mt-1 text-slate-300">{result.reason}</p>
            </div>
          </>
        ) : (
          <p className="text-mission-muted">Not yet evaluated.</p>
        )}
      </div>
    </GlassPanel>
  );
}
