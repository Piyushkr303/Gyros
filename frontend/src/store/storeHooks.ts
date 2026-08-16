import { useReplayStore } from "./replayStore";
import { useReviewStore } from "./reviewStore";
import type { ReducerState } from "./eventReducer";

/** Bound-hook bundle so dashboard components (AgentGraphView, FindingsPage,
 * TokenDashboard, the inspector panels) can read from either the live
 * WebSocket-driven store or the historical Replay store without importing
 * a specific store directly - both stores extend ReducerState and are
 * driven by the same pure reducer (eventReducer.ts), so their shapes match
 * exactly; only *which* store backs the read differs. */
export interface ReducerStoreHooks {
  useAgents: () => ReducerState["agents"];
  useEdges: () => ReducerState["edges"];
  useFindings: () => ReducerState["findings"];
  useTokenRecords: () => ReducerState["tokenRecords"];
  useToolCalls: () => ReducerState["toolCalls"];
  useMessages: () => ReducerState["messages"];
  useEvents: () => ReducerState["events"];
}

export const liveStoreHooks: ReducerStoreHooks = {
  useAgents: () => useReviewStore((s) => s.agents),
  useEdges: () => useReviewStore((s) => s.edges),
  useFindings: () => useReviewStore((s) => s.findings),
  useTokenRecords: () => useReviewStore((s) => s.tokenRecords),
  useToolCalls: () => useReviewStore((s) => s.toolCalls),
  useMessages: () => useReviewStore((s) => s.messages),
  useEvents: () => useReviewStore((s) => s.events),
};

export const replayStoreHooks: ReducerStoreHooks = {
  useAgents: () => useReplayStore((s) => s.agents),
  useEdges: () => useReplayStore((s) => s.edges),
  useFindings: () => useReplayStore((s) => s.findings),
  useTokenRecords: () => useReplayStore((s) => s.tokenRecords),
  useToolCalls: () => useReplayStore((s) => s.toolCalls),
  useMessages: () => useReplayStore((s) => s.messages),
  useEvents: () => useReplayStore((s) => s.events),
};
