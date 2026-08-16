import { useState } from "react";

import { AgentGraphView } from "../../components/AgentGraph/AgentGraphView";
import { AgentInspectorPanel } from "../../components/AgentInspector/AgentInspectorPanel";
import { ConditionInspectorPanel } from "../../components/ConditionInspector/ConditionInspectorPanel";

export function AgentGraphPage() {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);

  return (
    <div className="grid h-[calc(100vh-140px)] grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
      <AgentGraphView
        onSelectAgent={(id) => {
          setSelectedAgent(id);
          setSelectedEdge(null);
        }}
        onSelectEdge={(id) => {
          setSelectedEdge(id);
          setSelectedAgent(null);
        }}
      />
      <div className="space-y-4 overflow-y-auto">
        <AgentInspectorPanel agentId={selectedAgent} />
        <ConditionInspectorPanel edgeId={selectedEdge} />
      </div>
    </div>
  );
}
