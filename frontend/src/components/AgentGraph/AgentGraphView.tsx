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
import { Pause, Play } from "lucide-react";

import type { AgentStatus, ReviewEvent } from "../../types/domain";
import type { AgentNodeState, EdgeVisualState } from "../../store/eventReducer";
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

const NODE_WIDTH = 190;
const NODE_HEIGHT = 64;
const FOCUS_ZOOM = 1.15;
// A slow, deliberate pan/zoom reads as "the camera is showing me something"
// rather than "the UI is glitching" - mock-mode agents can finish in well
// under a second, so speed has to come from the camera's own pacing, not
// from how fast the underlying events fire.
const FOCUS_DURATION_MS = 1100;
// Minimum time the camera stays on one node before it's allowed to move to
// the next, regardless of how fast agents actually transition. Without this,
// a burst of quick agent completions (common in mock mode) makes the camera
// whip across the graph faster than a viewer can follow.
const MIN_DWELL_MS = 1600;

// Statuses that mean "this agent is actively doing work right now" - kept in
// sync with the glow states in AgentNode's STATUS_STYLE.
const PROCESSING_STATUSES = new Set<AgentStatus>([
  "RUNNING",
  "THINKING_SUMMARY",
  "CALLING_TOOL",
  "COMMUNICATING",
  "VALIDATING",
]);

function layout(nodeIds: string[], edgePairs: Array<[string, string]>) {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "TB", nodesep: 60, ranksep: 90 });
  g.setDefaultEdgeLabel(() => ({}));

  nodeIds.forEach((id) => g.setNode(id, { width: NODE_WIDTH, height: NODE_HEIGHT }));
  edgePairs.forEach(([source, target]) => {
    if (source !== target) g.setEdge(source, target);
  });

  dagre.layout(g);

  const positions: Record<string, { x: number; y: number }> = {};
  nodeIds.forEach((id) => {
    const pos = g.node(id);
    positions[id] = { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 };
  });
  return positions;
}

/** Walks the event log newest-first to find the agent that most recently
 * became active and is still in a processing state - this is "the node
 * currently being worked on" that the camera should follow. Falling back to
 * event order (rather than just scanning `agents`) means that when several
 * agents are active at once, focus follows whichever one moved last instead
 * of jumping unpredictably based on object key order. */
function findActiveAgentId(events: ReviewEvent[], agents: Record<string, AgentNodeState>): string | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const agentId = events[i]?.payload?.agent;
    if (typeof agentId !== "string") continue;
    const status = agents[agentId]?.status;
    if (status && PROCESSING_STATUSES.has(status)) return agentId;
  }
  // Fallback: no event pointed at a live agent, but one may still be
  // active (e.g. right after a replay seek) - just take the first match.
  const fallback = Object.values(agents).find((a) => PROCESSING_STATUSES.has(a.status));
  return fallback ? fallback.id : null;
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

  const nodeIds = useMemo(() => Object.keys(agents), [Object.keys(agents).length]); // eslint-disable-line react-hooks/exhaustive-deps
  const edgeList = useMemo(() => Object.values(edges), [edges]);

  const positions = useMemo(
    () =>
      layout(
        nodeIds,
        edgeList.map((e) => [e.def.source_agent, e.def.target_agent])
      ),
    [nodeIds, edgeList.length] // eslint-disable-line react-hooks/exhaustive-deps
  );

  const rfNodes: Node<AgentNodeData>[] = nodeIds.map((id) => {
    const agent = agents[id];
    const pos = positions[id] ?? { x: 0, y: 0 };
    return {
      id,
      type: "agent",
      position: pos,
      data: {
        label: id.replace(/_/g, " "),
        status: agent.status,
        findingsCount: agent.findingsCount,
        dynamicallyActivated: agent.dynamicallyActivated,
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
      },
    };
  });

  const activeAgentId = findActiveAgentId(events, agents);
  const [autoFollow, setAutoFollow] = useState(true);
  const didInitialFit = useRef(false);
  const lastFocusedId = useRef<string | null>(null);
  const lastFocusAt = useRef(0);
  const pendingFocusTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestActiveIdRef = useRef(activeAgentId);
  latestActiveIdRef.current = activeAgentId;

  useEffect(() => {
    if (!didInitialFit.current) {
      // Let the very first render settle with the whole graph in view.
      didInitialFit.current = true;
      return;
    }
    if (!autoFollow || !activeAgentId || activeAgentId === lastFocusedId.current) return;

    const focus = (id: string) => {
      const pos = positions[id];
      if (!pos) return;
      lastFocusedId.current = id;
      lastFocusAt.current = Date.now();
      setCenter(pos.x + NODE_WIDTH / 2, pos.y + NODE_HEIGHT / 2, {
        zoom: FOCUS_ZOOM,
        duration: FOCUS_DURATION_MS,
      });
    };

    const elapsedSinceLastFocus = Date.now() - lastFocusAt.current;
    if (elapsedSinceLastFocus >= MIN_DWELL_MS) {
      focus(activeAgentId);
    } else if (!pendingFocusTimer.current) {
      // Already showing a node the viewer hasn't had time to register yet -
      // wait out the remainder of its dwell time, then jump to whichever
      // agent is active *then* (not necessarily this one).
      pendingFocusTimer.current = setTimeout(() => {
        pendingFocusTimer.current = null;
        if (latestActiveIdRef.current && latestActiveIdRef.current !== lastFocusedId.current) {
          focus(latestActiveIdRef.current);
        }
      }, MIN_DWELL_MS - elapsedSinceLastFocus);
    }
  }, [activeAgentId, autoFollow, positions, setCenter]);

  useEffect(() => {
    lastFocusedId.current = null;
    lastFocusAt.current = 0;
    if (pendingFocusTimer.current) {
      clearTimeout(pendingFocusTimer.current);
      pendingFocusTimer.current = null;
    }
  }, [nodeIds]);

  useEffect(
    () => () => {
      if (pendingFocusTimer.current) clearTimeout(pendingFocusTimer.current);
    },
    []
  );

  return (
    <ReactFlow
      nodes={rfNodes}
      edges={rfEdges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      onNodeClick={(_, node) => onSelectAgent(node.id)}
      onEdgeClick={(_, edge) => onSelectEdge(edge.id)}
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
      <Panel position="top-right" className="!m-3">
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
