import { create } from "zustand";

import type { ConditionalEdgeDef, GraphNodeDef, ReviewEvent } from "../types/domain";
import { applyEventToState, emptyAgentState, emptyReducerState, type ReducerState } from "./eventReducer";

export type { AgentNodeState, AgentMessageEntry, EdgeRuntimeState, EdgeVisualState, ToolCallState } from "./eventReducer";

interface ReviewStoreState extends ReducerState {
  reviewId: string | null;
  connectionStatus: "idle" | "connecting" | "open" | "closed";

  setReviewId: (id: string | null) => void;
  setConnectionStatus: (status: ReviewStoreState["connectionStatus"]) => void;
  setTopology: (nodes: GraphNodeDef[], edges: ConditionalEdgeDef[]) => void;
  applyEvent: (event: ReviewEvent) => void;
  reset: () => void;
}

export const useReviewStore = create<ReviewStoreState>((set, get) => ({
  reviewId: null,
  connectionStatus: "idle",
  ...emptyReducerState(),

  setReviewId: (id) => set({ reviewId: id }),
  setConnectionStatus: (status) => set({ connectionStatus: status }),

  setTopology: (nodes, edges) => {
    const agents: ReviewStoreState["agents"] = {};
    for (const n of nodes) agents[n.id] = emptyAgentState(n.id);

    const edgeState: ReviewStoreState["edges"] = {};
    for (const e of edges) {
      edgeState[e.edge_id] = { def: e, state: "idle" };
    }
    set({ agents, edges: edgeState });
  },

  applyEvent: (event) => set(applyEventToState(get(), event)),

  reset: () => set(emptyReducerState()),
}));
