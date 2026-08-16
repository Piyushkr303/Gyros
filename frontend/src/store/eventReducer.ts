import type {
  AgentStatus,
  ConditionalEdgeDef,
  EdgeEvaluationResult,
  Finding,
  ReviewEvent,
  ThinkingSummary,
  TokenUsageRecord,
} from "../types/domain";

export interface AgentNodeState {
  id: string;
  status: AgentStatus;
  lastSummary?: ThinkingSummary;
  findingsCount: number;
  durationMs?: number;
  error?: string;
  skippedReason?: string;
  dynamicallyActivated?: boolean;
  activationReason?: string;
}

export type EdgeVisualState = "idle" | "active" | "passed" | "failed" | "skipped";

export interface EdgeRuntimeState {
  def: ConditionalEdgeDef;
  state: EdgeVisualState;
  lastResult?: EdgeEvaluationResult;
}

export interface ToolCallState {
  agent: string;
  tool: string;
  status: "running" | "success" | "failed";
  durationMs?: number;
  error?: string | null;
  startedAt: number;
}

export interface AgentMessageEntry {
  message_id: string;
  sender: string;
  receiver: string;
  type: string;
  finding_id: string | null;
  summary: string;
  confidence: number | null;
  timestamp: string;
}

export const MAX_EVENTS = 500;
const MAX_TOOL_CALLS = 100;
const MAX_MESSAGES = 100;

export interface ReducerState {
  agents: Record<string, AgentNodeState>;
  edges: Record<string, EdgeRuntimeState>;
  findings: Record<string, Finding>;
  tokenRecords: TokenUsageRecord[];
  toolCalls: ToolCallState[];
  messages: AgentMessageEntry[];
  events: ReviewEvent[];
  approvalRequired: boolean;
  reviewStatus: string | null;
  mockBanner: { groq: boolean; github: boolean };
}

export function emptyAgentState(id: string): AgentNodeState {
  return { id, status: "IDLE", findingsCount: 0 };
}

export function emptyReducerState(): ReducerState {
  return {
    agents: {},
    edges: {},
    findings: {},
    tokenRecords: [],
    toolCalls: [],
    messages: [],
    events: [],
    approvalRequired: false,
    reviewStatus: null,
    mockBanner: { groq: false, github: false },
  };
}

/** Pure reducer: (state, event) -> new state. Shared by the live WS-driven
 * store and the historical Replay store so both interpret the exact same
 * event vocabulary identically - replaying a past review's events produces
 * the same derived UI state as watching it live did. */
export function applyEventToState(state: ReducerState, event: ReviewEvent): ReducerState {
  const events = [...state.events, event].slice(-MAX_EVENTS);
  const payload = event.payload ?? {};
  const agents = { ...state.agents };
  const edges = { ...state.edges };
  let findings = state.findings;
  let tokenRecords = state.tokenRecords;
  let toolCalls = state.toolCalls;
  let messages = state.messages;
  let approvalRequired = state.approvalRequired;
  let reviewStatus = state.reviewStatus;
  let mockBanner = state.mockBanner;

  const touchAgent = (name: string, patch: Partial<AgentNodeState>) => {
    const existing = agents[name] ?? emptyAgentState(name);
    agents[name] = { ...existing, ...patch };
  };

  switch (event.type) {
    case "AGENT_STARTED":
      touchAgent(payload.agent, { status: "RUNNING", error: undefined, skippedReason: undefined });
      break;
    case "AGENT_DYNAMICALLY_ACTIVATED":
      touchAgent(payload.agent, { dynamicallyActivated: true, activationReason: payload.reason });
      break;
    case "AGENT_TOOL_STARTED": {
      touchAgent(payload.agent, { status: "CALLING_TOOL" });
      toolCalls = [
        ...toolCalls,
        { agent: payload.agent, tool: payload.tool, status: "running" as const, startedAt: Date.now() },
      ].slice(-MAX_TOOL_CALLS);
      break;
    }
    case "AGENT_TOOL_COMPLETED": {
      touchAgent(payload.agent, { status: "RUNNING" });
      const updated = [...toolCalls];
      for (let i = updated.length - 1; i >= 0; i--) {
        if (updated[i].agent === payload.agent && updated[i].tool === payload.tool && updated[i].status === "running") {
          updated[i] = {
            ...updated[i],
            status: payload.success ? "success" : "failed",
            durationMs: payload.duration_ms,
            error: payload.error,
          };
          break;
        }
      }
      toolCalls = updated;
      break;
    }
    case "AGENT_THINKING_SUMMARY":
      touchAgent(payload.agent, { lastSummary: payload.summary, status: "THINKING_SUMMARY" });
      break;
    case "AGENT_COMPLETED":
      touchAgent(payload.agent, {
        status: "COMPLETED",
        findingsCount: payload.findings ?? agents[payload.agent]?.findingsCount ?? 0,
        durationMs: payload.duration_ms,
      });
      break;
    case "AGENT_FAILED":
      touchAgent(payload.agent, { status: "FAILED", error: payload.error });
      break;
    case "AGENT_SKIPPED":
      touchAgent(payload.agent, { status: "SKIPPED", skippedReason: payload.reason });
      break;
    case "AGENT_MESSAGE_SENT": {
      const m = payload.message;
      messages = [
        ...messages,
        {
          message_id: m.message_id,
          sender: m.sender,
          receiver: m.receiver,
          type: m.type,
          finding_id: m.finding_id,
          summary: m.summary,
          confidence: m.confidence,
          timestamp: m.timestamp,
        },
      ].slice(-MAX_MESSAGES);
      break;
    }
    case "EDGE_EVALUATED": {
      const edgeId = payload.edge.edge_id;
      const existing = edges[edgeId];
      edges[edgeId] = existing
        ? { ...existing, lastResult: payload.result }
        : { def: payload.edge, state: "idle", lastResult: payload.result };
      break;
    }
    case "EDGE_TRIGGERED": {
      const edgeId = payload.edge.edge_id;
      const existing = edges[edgeId] ?? { def: payload.edge, state: "idle" as const };
      edges[edgeId] = { ...existing, state: "passed", lastResult: payload.result };
      break;
    }
    case "EDGE_SKIPPED": {
      const edgeId = payload.edge.edge_id;
      const existing = edges[edgeId] ?? { def: payload.edge, state: "idle" as const };
      edges[edgeId] = { ...existing, state: "failed", lastResult: payload.result };
      break;
    }
    case "FINDING_CREATED":
    case "FINDING_VALIDATED":
    case "FINDING_REJECTED":
    case "FINDING_CRITICIZED": {
      const f: Finding = payload.finding;
      findings = { ...findings, [f.id]: f };
      break;
    }
    case "TOKEN_USAGE_RECORDED": {
      const record: TokenUsageRecord = payload.record;
      tokenRecords = [...tokenRecords, record];
      if (record.provider_mode === "mock") {
        mockBanner = { ...mockBanner, groq: true };
      }
      break;
    }
    case "GITHUB_UPDATED": {
      const result = payload.result ?? {};
      if (result.id && String(result.id).startsWith("mock-")) {
        mockBanner = { ...mockBanner, github: true };
      }
      break;
    }
    case "APPROVAL_REQUIRED":
      approvalRequired = true;
      break;
    case "APPROVAL_DECIDED":
      approvalRequired = false;
      break;
    case "REVIEW_COMPLETED":
      reviewStatus = payload.status;
      break;
    case "REVIEW_FAILED":
      reviewStatus = "FAILED";
      break;
    default:
      break;
  }

  return { agents, edges, findings, tokenRecords, toolCalls, messages, events, approvalRequired, reviewStatus, mockBanner };
}
