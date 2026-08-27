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
  /** Set when this edge sits on a branch no live path reaches (yet) - fades
   * it out of the way of whatever path is actually executing. */
  dimmed?: boolean;
}

const STATE_STYLE: Record<EdgeVisualState, { stroke: string; strokeWidth: number; dash?: string }> = {
  idle: { stroke: "#1c2333", strokeWidth: 1.5, dash: "4 4" },
  active: { stroke: "#818cf8", strokeWidth: 3 },
  passed: { stroke: "#4ade80", strokeWidth: 3 },
  failed: { stroke: "#f87171", strokeWidth: 1.5, dash: "2 4" },
  skipped: { stroke: "#334155", strokeWidth: 1, dash: "2 6" },
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
  const opacity = data?.dimmed ? 0.3 : 1;

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
          opacity,
          transition: "stroke 0.3s ease, stroke-width 0.3s ease, d 0.3s ease, opacity 0.4s ease",
        }}
      />
      {/* A pair of dots travels the path while data is actually flowing through this
          edge, staggered half a cycle apart for a continuous "in transit" read rather
          than the generic marching-ants dash pattern. */}
      {state === "active" && !data?.dimmed && (
        <>
          <circle r="3.5" fill={style.stroke}>
            <animateMotion dur="1.6s" repeatCount="indefinite" path={edgePath} />
          </circle>
          <circle r="3.5" fill={style.stroke} opacity={0.6}>
            <animateMotion dur="1.6s" begin="-0.8s" repeatCount="indefinite" path={edgePath} />
          </circle>
        </>
      )}
      {isConditional && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              transition: "transform 0.3s ease, opacity 0.4s ease",
              opacity,
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
