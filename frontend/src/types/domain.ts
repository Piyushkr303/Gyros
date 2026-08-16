export type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type ValidationStatus = "PENDING" | "CONFIRMED" | "REJECTED" | "UNCERTAIN";

export type CriticStatus = "PENDING" | "ACCEPTED" | "WEAK_EVIDENCE" | "DUPLICATE" | "FALSE_POSITIVE";

export type IncrementalStatus = "NEW" | "RESOLVED" | "UNCHANGED" | "STALE" | "INVALIDATED";

export interface Finding {
  id: string;
  review_id: string;
  severity: Severity;
  category: string;
  file: string;
  line: number | null;
  title: string;
  description: string;
  evidence_ids: string[];
  impact: string;
  recommendation: string;
  confidence: number;
  detecting_agent: string;
  validator_status: ValidationStatus;
  validator_confidence: number | null;
  critic_status: CriticStatus;
  critic_notes: string | null;
  reanalysis_count: number;
  incremental_status: IncrementalStatus | null;
  carried_from: string | null;
  debate_resolution: string | null;
  created_at: string;
  updated_at: string;
}

export interface Evidence {
  evidence_id: string;
  review_id: string;
  source: string;
  agent: string;
  tool: string | null;
  file: string | null;
  line: number | null;
  result: string;
  confidence: number | null;
  timestamp: string;
}

export type AgentStatus =
  | "IDLE"
  | "QUEUED"
  | "RUNNING"
  | "THINKING_SUMMARY"
  | "CALLING_TOOL"
  | "WAITING"
  | "COMMUNICATING"
  | "VALIDATING"
  | "FAILED"
  | "COMPLETED"
  | "SKIPPED";

export interface ThinkingSummary {
  objective: string;
  decision: string;
  action: string;
  tool: string | null;
  observation: string;
  next_action: string;
}

export type ConditionType =
  | "ALWAYS"
  | "IF"
  | "ELSE"
  | "AND"
  | "OR"
  | "NOT"
  | "THRESHOLD"
  | "EVENT"
  | "AGENT_RESULT"
  | "TOOL_RESULT";

export interface ConditionalEdgeDef {
  edge_id: string;
  source_agent: string;
  target_agent: string;
  condition: string;
  condition_type: ConditionType;
  priority: number;
  enabled: boolean;
}

export interface EdgeEvaluationResult {
  edge_id: string;
  review_id: string;
  passed: boolean;
  value: unknown;
  reason: string;
  evaluated_at: string;
}

export interface GraphNodeDef {
  id: string;
  label: string;
  kind: "agent" | "orchestration";
}

export interface TokenUsageRecord {
  id: string;
  review_id: string;
  agent: string;
  input_tokens: number;
  output_tokens: number;
  model: string | null;
  llm_call_avoided: boolean;
  avoided_reason: string | null;
  provider_mode: "real" | "mock";
  timestamp: string;
}

export type EventType =
  | "WEBHOOK_RECEIVED"
  | "WEBHOOK_REJECTED"
  | "PR_LOADED"
  | "PLANNING_STARTED"
  | "AGENT_QUEUED"
  | "AGENT_STARTED"
  | "AGENT_THINKING_SUMMARY"
  | "AGENT_TOOL_STARTED"
  | "AGENT_TOOL_COMPLETED"
  | "AGENT_MESSAGE_SENT"
  | "AGENT_MESSAGE_RECEIVED"
  | "AGENT_COMPLETED"
  | "AGENT_FAILED"
  | "AGENT_SKIPPED"
  | "EDGE_EVALUATED"
  | "EDGE_TRIGGERED"
  | "EDGE_SKIPPED"
  | "FINDING_CREATED"
  | "FINDING_VALIDATED"
  | "FINDING_REJECTED"
  | "FINDING_CRITICIZED"
  | "REPLAN_STARTED"
  | "REPLAN_COMPLETED"
  | "CONFLICT_DETECTED"
  | "DEBATE_STARTED"
  | "DEBATE_RESOLVED"
  | "HIGH_SEVERITY_FINDING_CONFIRMED"
  | "AGENT_DYNAMICALLY_ACTIVATED"
  | "REVIEW_GENERATED"
  | "APPROVAL_REQUIRED"
  | "APPROVAL_DECIDED"
  | "GITHUB_UPDATED"
  | "TOKEN_USAGE_RECORDED"
  | "REVIEW_FAILED"
  | "REVIEW_COMPLETED"
  | "CHAOS_FAILURE_INJECTED"
  | "CHAOS_RETRY_SUCCEEDED"
  | "TOOL_RESULT_CACHE_HIT"
  | "INCREMENTAL_REVIEW_STARTED"
  | "FINDING_CLASSIFIED"
  | "INCREMENTAL_REVIEW_COMPLETED"
  | "JIRA_UPDATED";

export interface ReviewEvent {
  id: string;
  type: EventType;
  review_id: string;
  timestamp: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload: any;
}

export interface ReviewSession {
  review_id: string;
  pr_number: number;
  repo: string;
  pr_title: string;
  head_sha: string;
  base_sha: string;
  status: string;
  previous_review_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface PRFile {
  filename: string;
  status: string;
  additions: number;
  deletions: number;
  changes: number;
  patch: string | null;
}
