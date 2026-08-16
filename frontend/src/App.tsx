import { Suspense, lazy, useState } from "react";
import {
  Activity,
  BarChart3,
  CheckCircle2,
  Clock,
  Code2,
  GitBranch,
  GitPullRequest,
  ListChecks,
  Network,
  ScrollText,
  ShieldCheck,
  Zap,
} from "lucide-react";

import { DashboardPage } from "./pages/Dashboard/DashboardPage";
import { AgentGraphPage } from "./pages/AgentGraph/AgentGraphPage";
import { FindingsPage } from "./pages/Findings/FindingsPage";
import { ValidationPage } from "./pages/Validation/ValidationPage";
import { ConditionsPage } from "./pages/Conditions/ConditionsPage";
import { TracesPage } from "./pages/Traces/TracesPage";
import { MetricsPage } from "./pages/Metrics/MetricsPage";
import { ApprovalPage } from "./pages/Approval/ApprovalPage";
import type { ExplorerTarget } from "./pages/CodeExplorer/CodeExplorerPage";
import { TokenDashboard } from "./components/TokenDashboard/TokenDashboard";
import { api } from "./services/api";
import { connectReviewSocket } from "./services/websocket";
import { useReviewStore } from "./store/reviewStore";

// Code-split: both pull in Monaco / the full dashboard chrome, which most
// sessions never open - keep them out of the initial bundle.
const CodeExplorerPage = lazy(() =>
  import("./pages/CodeExplorer/CodeExplorerPage").then((m) => ({ default: m.CodeExplorerPage }))
);
const ReplayPage = lazy(() => import("./pages/Replay/ReplayPage").then((m) => ({ default: m.ReplayPage })));

type Tab =
  | "dashboard"
  | "graph"
  | "findings"
  | "validation"
  | "conditions"
  | "traces"
  | "metrics"
  | "explorer"
  | "replay"
  | "tokens"
  | "approval";

const TABS: Array<{ id: Tab; label: string; icon: typeof Activity }> = [
  { id: "dashboard", label: "Dashboard", icon: Activity },
  { id: "graph", label: "Agent Graph", icon: Network },
  { id: "findings", label: "Findings", icon: ListChecks },
  { id: "validation", label: "Validation", icon: CheckCircle2 },
  { id: "conditions", label: "Conditions", icon: GitBranch },
  { id: "traces", label: "Traces", icon: ScrollText },
  { id: "metrics", label: "Metrics", icon: BarChart3 },
  { id: "explorer", label: "Code", icon: Code2 },
  { id: "replay", label: "Replay", icon: Clock },
  { id: "tokens", label: "Tokens", icon: Zap },
  { id: "approval", label: "Approval", icon: ShieldCheck },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [triggering, setTriggering] = useState(false);
  const [triggeringFollowup, setTriggeringFollowup] = useState(false);
  const [followupError, setFollowupError] = useState<string | null>(null);
  const [explorerTarget, setExplorerTarget] = useState<ExplorerTarget | null>(null);
  const connectionStatus = useReviewStore((s) => s.connectionStatus);
  const reviewId = useReviewStore((s) => s.reviewId);
  const setTopology = useReviewStore((s) => s.setTopology);

  function openInExplorer(file: string, line: number | null) {
    setExplorerTarget({ file, line });
    setTab("explorer");
  }

  async function triggerDemo() {
    setTriggering(true);
    setFollowupError(null);
    try {
      const { review_id } = await api.triggerDemo();
      connectReviewSocket(review_id);
      const topology = await api.getGraphTopology(review_id);
      setTopology(topology.nodes, topology.edges);
    } catch (err) {
      console.error("Failed to trigger demo review", err);
    } finally {
      setTriggering(false);
    }
  }

  async function triggerDemoFollowup() {
    setTriggeringFollowup(true);
    setFollowupError(null);
    try {
      const { review_id } = await api.triggerDemoFollowup();
      connectReviewSocket(review_id);
      const topology = await api.getGraphTopology(review_id);
      setTopology(topology.nodes, topology.edges);
    } catch (err) {
      setFollowupError(
        "No prior demo review to follow up on yet - trigger the initial demo review first."
      );
      console.error("Failed to trigger follow-up review", err);
    } finally {
      setTriggeringFollowup(false);
    }
  }

  return (
    <div className="min-h-screen px-6 py-5">
      <header className="mb-5 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <GitPullRequest className="h-6 w-6 text-mission-accent" />
          <div>
            <h1 className="font-display text-base font-semibold tracking-wide text-slate-100">
              MULTI-AGENT PR REVIEWER
            </h1>
            <p className="text-[11px] text-mission-muted">Autonomous engineering review, observed live</p>
          </div>
        </div>

        <nav className="ml-4 flex gap-1">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-display uppercase tracking-wide transition-colors ${
                tab === id ? "bg-mission-accent/10 text-mission-accent" : "text-mission-muted hover:text-slate-200"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <span className="flex items-center gap-1.5 text-[11px] text-mission-muted">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                connectionStatus === "open" ? "bg-mission-ok" : connectionStatus === "connecting" ? "bg-mission-warn" : "bg-mission-muted"
              }`}
            />
            {connectionStatus}
            {reviewId ? ` · ${reviewId}` : ""}
          </span>
          {followupError && <span className="text-[11px] text-mission-danger">{followupError}</span>}
          <button
            onClick={triggerDemo}
            disabled={triggering}
            className="rounded-lg border border-mission-accent/40 bg-mission-accent/10 px-3 py-1.5 text-xs font-display uppercase tracking-wide text-mission-accent transition hover:bg-mission-accent/20 disabled:opacity-50"
          >
            {triggering ? "Starting..." : "Trigger Demo Review"}
          </button>
          <button
            onClick={triggerDemoFollowup}
            disabled={triggeringFollowup}
            title="Simulates a second push to the same demo PR and runs an incremental (delta-only) review chained to the most recent one"
            className="rounded-lg border border-mission-border px-3 py-1.5 text-xs font-display uppercase tracking-wide text-mission-muted transition hover:text-slate-200 disabled:opacity-50"
          >
            {triggeringFollowup ? "Starting..." : "Trigger Follow-up Push"}
          </button>
        </div>
      </header>

      <main>
        {tab === "dashboard" && <DashboardPage />}
        {tab === "graph" && <AgentGraphPage />}
        {tab === "findings" && <FindingsPage onOpenInExplorer={openInExplorer} />}
        {tab === "validation" && <ValidationPage />}
        {tab === "conditions" && <ConditionsPage />}
        {tab === "traces" && <TracesPage />}
        {tab === "metrics" && <MetricsPage />}
        {tab === "explorer" && (
          <Suspense fallback={<p className="text-xs text-mission-muted">Loading Code Explorer...</p>}>
            <CodeExplorerPage target={explorerTarget} />
          </Suspense>
        )}
        {tab === "replay" && (
          <Suspense fallback={<p className="text-xs text-mission-muted">Loading Replay...</p>}>
            <ReplayPage />
          </Suspense>
        )}
        {tab === "tokens" && <TokenDashboard />}
        {tab === "approval" && <ApprovalPage />}
      </main>
    </div>
  );
}
