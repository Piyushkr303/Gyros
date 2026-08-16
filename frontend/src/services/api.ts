import type {
  ConditionalEdgeDef,
  Evidence,
  Finding,
  GraphNodeDef,
  PRFile,
  ReviewEvent,
  ReviewSession,
  TokenUsageRecord,
} from "../types/domain";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listReviews: () => request<ReviewSession[]>("/api/reviews"),
  getReview: (reviewId: string) => request<ReviewSession>(`/api/reviews/${reviewId}`),
  getFindings: (reviewId: string) => request<Finding[]>(`/api/reviews/${reviewId}/findings`),
  getEvidence: (reviewId: string) => request<Evidence[]>(`/api/reviews/${reviewId}/evidence`),
  getTokenUsage: (reviewId: string) => request<TokenUsageRecord[]>(`/api/reviews/${reviewId}/tokens`),
  getGraphTopology: (reviewId: string) =>
    request<{ nodes: GraphNodeDef[]; edges: ConditionalEdgeDef[] }>(`/api/reviews/${reviewId}/graph`),
  getEvents: (reviewId: string) => request<ReviewEvent[]>(`/api/reviews/${reviewId}/events`),
  getFiles: (reviewId: string) => request<PRFile[]>(`/api/reviews/${reviewId}/files`),
  getFileContent: (reviewId: string, path: string) =>
    request<{ path: string; ref: string; content: string }>(
      `/api/reviews/${reviewId}/files/content?path=${encodeURIComponent(path)}`,
    ),
  triggerDemo: () => request<{ review_id: string; status: string }>("/api/reviews/trigger-demo", { method: "POST" }),
  triggerDemoFollowup: () =>
    request<{ review_id: string; status: string; previous_review_id: string }>(
      "/api/reviews/trigger-demo-followup",
      { method: "POST" },
    ),
  approve: (reviewId: string) => request(`/api/reviews/${reviewId}/approve`, { method: "POST" }),
  reject: (reviewId: string) => request(`/api/reviews/${reviewId}/reject`, { method: "POST" }),
};

export function wsUrl(reviewId: string): string {
  const base = import.meta.env.VITE_WS_BASE_URL ?? "ws://localhost:8000";
  return `${base}/ws/reviews/${reviewId}`;
}
