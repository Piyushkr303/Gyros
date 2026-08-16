import { useMemo } from "react";
import dagre from "dagre";
import ReactFlow, { Background, Controls, MarkerType, type Edge, type Node } from "reactflow";
import "reactflow/dist/style.css";

import { liveStoreHooks, type ReducerStoreHooks } from "../../store/storeHooks";
import { AgentNode, type AgentNodeData } from "./nodes/AgentNode";
import { ConditionalEdgeComponent, type ConditionalEdgeData } from "../ConditionalEdge/ConditionalEdge";

const nodeTypes = { agent: AgentNode };
const edgeTypes = { conditional: ConditionalEdgeComponent };

const NODE_WIDTH = 190;
const NODE_HEIGHT = 64;

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

interface Props {
  onSelectAgent: (agentId: string) => void;
  onSelectEdge: (edgeId: string) => void;
  hooks?: ReducerStoreHooks;
}

export function AgentGraphView({ onSelectAgent, onSelectEdge, hooks = liveStoreHooks }: Props) {
  const agents = hooks.useAgents();
  const edges = hooks.useEdges();

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

  const rfEdges: Edge<ConditionalEdgeData>[] = edgeList.map((edge) => ({
    id: edge.def.edge_id,
    source: edge.def.source_agent,
    target: edge.def.target_agent,
    type: "conditional",
    markerEnd: { type: MarkerType.ArrowClosed, color: "#334155" },
    data: {
      condition: edge.def.condition,
      conditionType: edge.def.condition_type,
      state: edge.state,
    },
  }));

  return (
    <div className="glass-panel h-full w-full overflow-hidden">
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodeClick={(_, node) => onSelectAgent(node.id)}
        onEdgeClick={(_, edge) => onSelectEdge(edge.id)}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#141a29" gap={20} />
        <Controls className="!bg-mission-panel !border-mission-border" />
      </ReactFlow>
    </div>
  );
}
