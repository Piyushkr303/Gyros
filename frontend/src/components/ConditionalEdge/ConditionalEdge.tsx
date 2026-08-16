import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type EdgeProps } from "reactflow";

import type { EdgeVisualState } from "../../store/reviewStore";

export interface ConditionalEdgeData {
  condition: string;
  conditionType: string;
  state: EdgeVisualState;
}

const STATE_STYLE: Record<EdgeVisualState, { stroke: string; strokeWidth: number; dash?: string; animated: boolean }> = {
  idle: { stroke: "#1c2333", strokeWidth: 1.5, dash: "4 4", animated: false },
  active: { stroke: "#818cf8", strokeWidth: 3, animated: true },
  passed: { stroke: "#4ade80", strokeWidth: 3, animated: false },
  failed: { stroke: "#f87171", strokeWidth: 1.5, dash: "2 4", animated: false },
  skipped: { stroke: "#334155", strokeWidth: 1, dash: "2 6", animated: false },
};

export function ConditionalEdgeComponent({
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
}: EdgeProps<ConditionalEdgeData>) {
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 12,
  });

  const state = data?.state ?? "idle";
  const style = STATE_STYLE[state];
  const isConditional = data?.conditionType && data.conditionType !== "ALWAYS";

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: style.stroke,
          strokeWidth: style.strokeWidth,
          strokeDasharray: style.dash,
          transition: "stroke 0.3s ease, stroke-width 0.3s ease",
        }}
      />
      {isConditional && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            }}
            className={`pointer-events-none rounded border px-1.5 py-0.5 font-display text-[9px] ${
              state === "passed"
                ? "border-mission-ok/40 bg-mission-ok/10 text-mission-ok"
                : state === "failed"
                  ? "border-mission-danger/30 bg-mission-danger/10 text-mission-danger"
                  : "border-mission-border bg-mission-panel text-mission-muted"
            }`}
          >
            {state === "passed" ? "✓ " : state === "failed" ? "✗ " : ""}
            {data?.condition}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
