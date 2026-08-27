import { useEffect, useMemo, useRef, useState } from "react";
import dagre from "dagre";
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  MiniMap,
  Panel,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
} from "reactflow";
import "reactflow/dist/style.css";
import { LayoutGrid, Pause, Play, Rows3 } from "lucide-react";

import type { AgentStatus, ReviewEvent } from "../../types/domain";
import type { AgentNodeState, EdgeRuntimeState, EdgeVisualState } from "../../store/eventReducer";
import { liveStoreHooks, type ReducerStoreHooks } from "../../store/storeHooks";
import { AgentNode, STATUS_META, type AgentNodeData } from "./nodes/AgentNode";
import { ConditionalEdgeComponent, type ConditionalEdgeData } from "../ConditionalEdge/ConditionalEdge";

const EDGE_STATE_COLOR: Record<EdgeVisualState, string> = {
  idle: "#334155",
  active: "#818cf8",
  passed: "#4ade80",
  failed: "#f87171",
  skipped: "#334155",
};

const LEGEND_STATUSES: AgentStatus[] = ["RUNNING", "CALLING_TOOL", "WAITING", "COMPLETED", "FAILED", "SKIPPED"];

const nodeTypes = { agent: AgentNode };
const edgeTypes = { conditional: ConditionalEdgeComponent };

const FULL_SIZE = { width: 190, height: 64, nodesep: 60, ranksep: 90 };
const COMPACT_SIZE = { width: 72, height: 72, nodesep: 36, ranksep: 56 };

const FOCUS_ZOOM = 1.15;
// A slow, deliberate pan/zoom reads as "the camera is showing me something"
// rather than "the UI is glitching" - mock-mode agents can finish in well
// under a second, so speed has to come from the camera's own pacing, not
// from how fast the underlying events fire.
const FOCUS_DURATION_MS = 850;
// Fixed time the camera spends on each stop of its tour before advancing to
// the next one. Deliberately NOT tied to how fast events actually arrive -
// a full demo-mode review can finish all ~20 agents in under two seconds,
// which is faster than any "wait for the next real event" scheme could ever
// look smooth at. Walking a fixed queue at a fixed pace instead means the
// camera always takes a full, readable tour of every agent that ran, however
// fast the backend actually finished - and for a slow/real run, it simply
// waits at POLL_MS granularity for the next agent to start.
const TOUR_STEP_MS = 1300;
const TOUR_POLL_MS = 400;
const ELAPSED_TICK_MS = 300;

// Statuses that mean "this agent is actively doing work right now" - kept in
// sync with the glow states in AgentNode's STATUS_META.
const PROCESSING_STATUSES = new Set<AgentStatus>([
  "RUNNING",
  "THINKING_SUMMARY",
  "CALLING_TOOL",
  "COMMUNICATING",
  "VALIDATING",
]);

const TERMINAL_EVENT_TYPES = new Set(["AGENT_COMPLETED", "AGENT_FAILED", "AGENT_SKIPPED"]);

function layout(nodeIds: string[], edgePairs: Array<[string, string]>, size: typeof FULL_SIZE) {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "TB", nodesep: size.nodesep, ranksep: size.ranksep });
  g.setDefaultEdgeLabel(() => ({}));

  nodeIds.forEach((id) => g.setNode(id, { width: size.width, height: size.height }));
  edgePairs.forEach(([source, target]) => {
    if (source !== target) g.setEdge(source, target);
  });

  dagre.layout(g);

  const positions: Record<string, { x: number; y: number }> = {};
  nodeIds.forEach((id) => {
    const pos = g.node(id);
    positions[id] = { x: pos.x - size.width / 2, y: pos.y - size.height / 2 };
  });
  return positions;
}

/** Every agent id in the order its AGENT_STARTED event first appeared - the
 * camera's tour stops, in visitation order. Built from the event log rather
 * than the `agents` map so the order is the true execution order (including
 * every agent in a parallel fan-out) instead of object-key order. */
function buildTourQueue(events: ReviewEvent[]): string[] {
  const seen = new Set<string>();
  const order: string[] = [];
  for (const event of events) {
    const agentId = event.payload?.agent;
    if (event.type === "AGENT_STARTED" && typeof agentId === "string" && !seen.has(agentId)) {
      seen.add(agentId);
      order.push(agentId);
    }
  }
  return order;
}

/** Walks the event log chronologically to find, for every agent currently in
 * a processing status, the timestamp its current processing streak began
 * (its last AGENT_STARTED, cleared on any terminal event) - used to render a
 * live elapsed-time readout on the node card. */
function getProcessingStartTimes(events: ReviewEvent[], agents: Record<string, AgentNodeState>): Record<string, number> {
  const starts: Record<string, number> = {};
  for (const event of events) {
    const agentId = event.payload?.agent;
    if (typeof agentId !== "string") continue;
    if (event.type === "AGENT_STARTED") {
      starts[agentId] = Date.parse(event.timestamp);
    } else if (TERMINAL_EVENT_TYPES.has(event.type)) {
      delete starts[agentId];
    }
  }
  const result: Record<string, number> = {};
  for (const id of Object.keys(starts)) {
    const status = agents[id]?.status;
    if (status && PROCESSING_STATUSES.has(status)) result[id] = starts[id];
  }
  return result;
}

/** BFS from every entry node (no incoming edges), following only edges that
 * aren't already known to be dead (skipped/failed). A node not reached this
 * way is sitting on a branch nothing live points at (yet) - the caller fades
 * it so the graph's actual live path reads clearly instead of looking like
 * an undifferentiated grid of boxes. */
function computeReachable(nodeIds: string[], edgeList: EdgeRuntimeState[]): Set<string> {
  const incomingCount = new Map<string, number>(nodeIds.map((id) => [id, 0]));
  edgeList.forEach((e) => {
    incomingCount.set(e.def.target_agent, (incomingCount.get(e.def.target_agent) ?? 0) + 1);
  });
  const roots = nodeIds.filter((id) => (incomingCount.get(id) ?? 0) === 0);

  const adjacency = new Map<string, string[]>();
  edgeList.forEach((e) => {
    if (e.state === "skipped" || e.state === "failed") return;
    const list = adjacency.get(e.def.source_agent) ?? [];
    list.push(e.def.target_agent);
    adjacency.set(e.def.source_agent, list);
  });

  const visited = new Set<string>(roots);
  const queue = [...roots];
  while (queue.length > 0) {
    const current = queue.shift()!;
    for (const next of adjacency.get(current) ?? []) {
      if (!visited.has(next)) {
        visited.add(next);
        queue.push(next);
      }
    }
  }
  return visited;
}

interface Props {
  onSelectAgent: (agentId: string) => void;
  onSelectEdge: (edgeId: string) => void;
  hooks?: ReducerStoreHooks;
}

function AgentGraphCanvas({ onSelectAgent, onSelectEdge, hooks = liveStoreHooks }: Props) {
  const agents = hooks.useAgents();
  const edges = hooks.useEdges();
  const events = hooks.useEvents();
  const { setCenter, fitView } = useReactFlow();

  const [autoFollow, setAutoFollow] = useState(true);
  const [compact, setCompact] = useState(false);
  const size = compact ? COMPACT_SIZE : FULL_SIZE;

  const nodeIds = useMemo(() => Object.keys(agents), [Object.keys(agents).length]); // eslint-disable-line react-hooks/exhaustive-deps
  const edgeList = useMemo(() => Object.values(edges), [edges]);

  const positions = useMemo(
    () =>
      layout(
        nodeIds,
        edgeList.map((e) => [e.def.source_agent, e.def.target_agent]),
        size
      ),
    [nodeIds, edgeList.length, compact] // eslint-disable-line react-hooks/exhaustive-deps
  );

  const reachable = useMemo(() => computeReachable(nodeIds, edgeList), [nodeIds, edgeList]);

  const processingStartTimes = useMemo(() => getProcessingStartTimes(events, agents), [events, agents]);
  const hasProcessing = Object.keys(processingStartTimes).length > 0;
  const [, forceElapsedTick] = useState(0);
  useEffect(() => {
    if (!hasProcessing) return;
    const id = setInterval(() => forceElapsedTick((t) => t + 1), ELAPSED_TICK_MS);
    return () => clearInterval(id);
  }, [hasProcessing]);

  const rfNodes: Node<AgentNodeData>[] = nodeIds.map((id) => {
    const agent = agents[id];
    const pos = positions[id] ?? { x: 0, y: 0 };
    const startedAt = processingStartTimes[id];
    const isDead = !reachable.has(id) && (agent.status === "IDLE" || agent.status === "QUEUED");
    return {
      id,
      type: "agent",
      position: pos,
      data: {
        label: id.replace(/_/g, " "),
        status: agent.status,
        findingsCount: agent.findingsCount,
        dynamicallyActivated: agent.dynamicallyActivated,
        elapsedMs: startedAt != null ? Date.now() - startedAt : undefined,
        dimmed: isDead,
        compact,
      },
    };
  });

  // Group edges by source->target pair so parallel edges between the same
  // two agents (the backend explicitly allows multiple conditional edges
  // per pair, see graph_config.py) can be visually fanned out instead of
  // rendering on top of one another with identical, ambiguous labels.
  const groupCounts = new Map<string, number>();
  edgeList.forEach((edge) => {
    const key = `${edge.def.source_agent}->${edge.def.target_agent}`;
    groupCounts.set(key, (groupCounts.get(key) ?? 0) + 1);
  });
  const groupSeen = new Map<string, number>();

  const rfEdges: Edge<ConditionalEdgeData>[] = edgeList.map((edge) => {
    const key = `${edge.def.source_agent}->${edge.def.target_agent}`;
    const parallelIndex = groupSeen.get(key) ?? 0;
    groupSeen.set(key, parallelIndex + 1);
    const parallelCount = groupCounts.get(key) ?? 1;
    const dimmed = !reachable.has(edge.def.source_agent) || !reachable.has(edge.def.target_agent);

    return {
      id: edge.def.edge_id,
      source: edge.def.source_agent,
      target: edge.def.target_agent,
      type: "conditional",
      markerEnd: { type: MarkerType.ArrowClosed, color: EDGE_STATE_COLOR[edge.state] },
      data: {
        condition: edge.def.condition,
        conditionType: edge.def.condition_type,
        state: edge.state,
        parallelIndex,
        parallelCount,
        dimmed,
      },
    };
  });

  const tourQueue = useMemo(() => buildTourQueue(events), [events]);

  // Everything the self-scheduling tour loop below needs to read is kept in
  // refs and updated every render, so the loop itself can run once (empty
  // dep array) instead of being torn down and restarted on every event -
  // that's what lets it keep its own steady pace independent of how often
  // the underlying store actually updates.
  const tourIndexRef = useRef(-1);
  const tourQueueRef = useRef(tourQueue);
  tourQueueRef.current = tourQueue;
  const autoFollowRef = useRef(autoFollow);
  autoFollowRef.current = autoFollow;
  const positionsRef = useRef(positions);
  positionsRef.current = positions;
  const sizeRef = useRef(size);
  sizeRef.current = size;
  const setCenterRef = useRef(setCenter);
  setCenterRef.current = setCenter;

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const tick = () => {
      if (cancelled) return;
      if (!autoFollowRef.current) {
        timer = setTimeout(tick, TOUR_POLL_MS);
        return;
      }
      const queue = tourQueueRef.current;
      const nextIndex = tourIndexRef.current + 1;
      if (nextIndex < queue.length) {
        tourIndexRef.current = nextIndex;
        const pos = positionsRef.current[queue[nextIndex]];
        if (pos) {
          const { width, height } = sizeRef.current;
          setCenterRef.current(pos.x + width / 2, pos.y + height / 2, {
            zoom: FOCUS_ZOOM,
            duration: FOCUS_DURATION_MS,
          });
        }
        timer = setTimeout(tick, TOUR_STEP_MS);
      } else {
        // Nothing new to visit yet - keep polling at a tighter interval so a
        // real (slower) run's next agent gets picked up promptly once it starts.
        timer = setTimeout(tick, TOUR_POLL_MS);
      }
    };

    // Small initial delay so the whole-graph fitView is visible for a beat
    // before the tour starts zooming in on the first agent.
    timer = setTimeout(tick, 500);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    tourIndexRef.current = -1;
  }, [nodeIds]);

  return (
    <ReactFlow
      nodes={rfNodes}
      edges={rfEdges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      onNodeClick={(_, node) => {
        // Selecting something to inspect is a signal the viewer wants to
        // read it, not have the camera pull away mid-read - pause following
        // until they explicitly resume it.
        setAutoFollow(false);
        onSelectAgent(node.id);
      }}
      onEdgeClick={(_, edge) => {
        setAutoFollow(false);
        onSelectEdge(edge.id);
      }}
      onInit={() => fitView({ duration: 0, padding: 0.3 })}
      fitView
      fitViewOptions={{ padding: 0.3 }}
      minZoom={0.35}
      maxZoom={1.75}
      nodesDraggable={false}
      nodesConnectable={false}
      selectNodesOnDrag={false}
      proOptions={{ hideAttribution: true }}
    >
      <Background variant={BackgroundVariant.Dots} color="#1c2333" gap={22} size={1.4} />
      <Controls
        showInteractive={false}
        className="!rounded-lg !border !border-mission-border !bg-mission-panel/90 !shadow-lg [&>button]:!border-mission-border [&>button]:!bg-transparent [&>button]:!text-slate-300 [&>button:hover]:!bg-mission-border/40"
      />
      <MiniMap
        pannable
        zoomable
        className="!rounded-lg !border !border-mission-border !bg-mission-panel/90"
        maskColor="rgba(5, 7, 13, 0.7)"
        nodeColor={(node) => STATUS_META[(node.data as AgentNodeData).status]?.color ?? "#475569"}
        nodeStrokeWidth={0}
        nodeBorderRadius={6}
      />
      <Panel
        position="top-left"
        className="!m-3 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-mission-border bg-mission-panel/90 px-3 py-2 backdrop-blur-sm"
      >
        {LEGEND_STATUSES.map((status) => (
          <span key={status} className="flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-mission-muted">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: STATUS_META[status].color, boxShadow: STATUS_META[status].pulse ? `0 0 6px ${STATUS_META[status].color}` : undefined }}
            />
            {STATUS_META[status].label}
          </span>
        ))}
      </Panel>
      <Panel position="top-right" className="!m-3 flex items-center gap-2">
        <button
          type="button"
          onClick={() => setCompact((v) => !v)}
          className="flex items-center gap-1.5 rounded-lg border border-mission-border bg-mission-panel/90 px-2.5 py-1.5 text-[10px] font-medium uppercase tracking-wide text-mission-muted backdrop-blur-sm transition-colors hover:text-slate-200"
          title={compact ? "Switch to full node cards" : "Switch to compact icon nodes"}
        >
          {compact ? <Rows3 className="h-3 w-3" /> : <LayoutGrid className="h-3 w-3" />}
          {compact ? "Compact" : "Full"}
        </button>
        <button
          type="button"
          onClick={() => setAutoFollow((v) => !v)}
          className="flex items-center gap-1.5 rounded-lg border border-mission-border bg-mission-panel/90 px-2.5 py-1.5 text-[10px] font-medium uppercase tracking-wide text-mission-muted backdrop-blur-sm transition-colors hover:text-slate-200"
          title={autoFollow ? "Pause camera auto-follow" : "Resume camera auto-follow"}
        >
          {autoFollow ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
          {autoFollow ? "Following" : "Paused"}
        </button>
      </Panel>
    </ReactFlow>
  );
}

export function AgentGraphView(props: Props) {
  return (
    <div className="glass-panel h-full w-full overflow-hidden">
      <ReactFlowProvider>
        <AgentGraphCanvas {...props} />
      </ReactFlowProvider>
    </div>
  );
}
