import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type EdgeProps } from "reactflow";

import type { EdgeVisualState } from "../../store/reviewStore";

export interface ConditionalEdgeData {
  condition: string;
  conditionType: string;
  state: EdgeVisualState;
  /** Position of this edge among other edges sharing the same source/target
   * pair, and how many such edges exist - used to fan out otherwise-identical
   * paths so their labels don't render on top of one another. */
  parallelIndex?: number;
  parallelCount?: number;
}

const STATE_STYLE: Record<EdgeVisualState, { stroke: string; strokeWidth: number; dash?: string; animated: boolean }> = {
  idle: { stroke: "#1c2333", strokeWidth: 1.5, dash: "4 4", animated: false },
  active: { stroke: "#818cf8", strokeWidth: 3, animated: true },
  passed: { stroke: "#4ade80", strokeWidth: 3, animated: false },
  failed: { stroke: "#f87171", strokeWidth: 1.5, dash: "2 4", animated: false },
  skipped: { stroke: "#334155", strokeWidth: 1, dash: "2 6", animated: false },
};

const PARALLEL_EDGE_SPACING = 64;
// Spread parallel edges' labels along the curve too (not just sideways), so
// a cluster of 3+ edges between the same pair doesn't pile their labels into
// one unreadable stack.
const PARALLEL_LABEL_T_STEP = 0.14;

/** Quadratic-bezier path whose control point is shifted horizontally by
 * `offset`, so edges that share a source/target pair separate visually
 * instead of stacking exactly on top of each other. Returns the path plus
 * the point on the curve at parameter `t` (0..1), where the label anchors -
 * staggering `t` per parallel edge keeps their labels from overlapping. */
function getOffsetPath(sourceX: number, sourceY: number, targetX: number, targetY: number, offset: number, t: number) {
  const controlX = (sourceX + targetX) / 2 + offset;
  const controlY = (sourceY + targetY) / 2;
  const path = `M${sourceX},${sourceY} Q ${controlX},${controlY} ${targetX},${targetY}`;
  // Point on a quadratic bezier: B(t) = (1-t)^2 P0 + 2(1-t)t P1 + t^2 P2
  const mt = 1 - t;
  const labelX = mt * mt * sourceX + 2 * mt * t * controlX + t * t * targetX;
  const labelY = mt * mt * sourceY + 2 * mt * t * controlY + t * t * targetY;
  return [path, labelX, labelY] as const;
}

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
  const parallelCount = data?.parallelCount ?? 1;
  const parallelIndex = data?.parallelIndex ?? 0;
  // Center the fan around 0: for 3 parallel edges, offsets are [-1, 0, 1] * spacing/step.
  const centeredIndex = parallelCount > 1 ? parallelIndex - (parallelCount - 1) / 2 : 0;
  const offset = centeredIndex * PARALLEL_EDGE_SPACING;
  const labelT = 0.5 + centeredIndex * PARALLEL_LABEL_T_STEP;

  const [edgePath, labelX, labelY] =
    offset === 0
      ? getSmoothStepPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition, borderRadius: 12 })
      : getOffsetPath(sourceX, sourceY, targetX, targetY, offset, labelT);

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
          strokeLinecap: "round",
          transition: "stroke 0.3s ease, stroke-width 0.3s ease, d 0.3s ease",
        }}
      />
      {isConditional && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              transition: "transform 0.3s ease",
            }}
            className={`pointer-events-none rounded-md border px-1.5 py-0.5 font-display text-[9px] shadow-sm backdrop-blur-sm ${
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
