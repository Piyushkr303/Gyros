import { useEffect, useState } from "react";
import { Pause, Play, SkipBack, SkipForward } from "lucide-react";

import { AgentGraphView } from "../../components/AgentGraph/AgentGraphView";
import { AgentInspectorPanel } from "../../components/AgentInspector/AgentInspectorPanel";
import { ConditionInspectorPanel } from "../../components/ConditionInspector/ConditionInspectorPanel";
import { TokenDashboard } from "../../components/TokenDashboard/TokenDashboard";
import { GlassPanel } from "../../components/common/GlassPanel";
import { FindingsPage } from "../Findings/FindingsPage";
import { api } from "../../services/api";
import { useReplayStore } from "../../store/replayStore";
import { replayStoreHooks } from "../../store/storeHooks";
import type { ReviewSession } from "../../types/domain";

const SPEEDS = [1, 2, 4, 8];

export function ReplayPage() {
  const [reviews, setReviews] = useState<ReviewSession[]>([]);
  const [selectedReview, setSelectedReview] = useState<string>("");
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);

  const reviewId = useReplayStore((s) => s.reviewId);
  const timeline = useReplayStore((s) => s.timeline);
  const cursor = useReplayStore((s) => s.cursor);
  const playing = useReplayStore((s) => s.playing);
  const speed = useReplayStore((s) => s.speed);
  const events = useReplayStore((s) => s.events);
  const load = useReplayStore((s) => s.load);
  const play = useReplayStore((s) => s.play);
  const pause = useReplayStore((s) => s.pause);
  const setSpeed = useReplayStore((s) => s.setSpeed);
  const stepForward = useReplayStore((s) => s.stepForward);
  const stepBackward = useReplayStore((s) => s.stepBackward);
  const seek = useReplayStore((s) => s.seek);

  useEffect(() => {
    api.listReviews().then(setReviews).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!playing) return;
    const interval = setInterval(() => stepForward(), 1000 / speed);
    return () => clearInterval(interval);
  }, [playing, speed, stepForward]);

  async function handleLoad() {
    if (!selectedReview) return;
    setLoadingEvents(true);
    setLoadError(null);
    try {
      const evts = await api.getEvents(selectedReview);
      load(selectedReview, evts);
      setSelectedAgent(null);
      setSelectedEdge(null);
    } catch (err) {
      setLoadError(String(err));
    } finally {
      setLoadingEvents(false);
    }
  }

  const latestEvent = events[events.length - 1];

  return (
    <div className="space-y-4">
      <GlassPanel title="Replay" subtitle="Step through a past review's real, persisted event history">
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={selectedReview}
            onChange={(e) => setSelectedReview(e.target.value)}
            className="rounded border border-mission-border bg-mission-panel px-2 py-1 text-xs text-slate-200"
          >
            <option value="">Select a review...</option>
            {reviews.map((r) => (
              <option key={r.review_id} value={r.review_id}>
                {r.review_id} — {r.pr_title || `PR #${r.pr_number}`} ({r.status})
              </option>
            ))}
          </select>
          <button
            onClick={handleLoad}
            disabled={!selectedReview || loadingEvents}
            className="rounded-lg border border-mission-accent/40 bg-mission-accent/10 px-3 py-1.5 text-xs font-display uppercase tracking-wide text-mission-accent transition hover:bg-mission-accent/20 disabled:opacity-50"
          >
            {loadingEvents ? "Loading..." : "Load"}
          </button>
          {loadError && <span className="text-xs text-mission-danger">{loadError}</span>}
        </div>

        {reviewId && (
          <div className="mt-4 space-y-2">
            <div className="flex items-center gap-2">
              <button
                onClick={stepBackward}
                disabled={cursor === 0}
                className="rounded border border-mission-border p-1.5 text-slate-200 disabled:opacity-30"
              >
                <SkipBack className="h-4 w-4" />
              </button>
              <button
                onClick={() => (playing ? pause() : play())}
                className="rounded border border-mission-accent/40 bg-mission-accent/10 p-1.5 text-mission-accent"
              >
                {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
              </button>
              <button
                onClick={stepForward}
                disabled={cursor >= timeline.length}
                className="rounded border border-mission-border p-1.5 text-slate-200 disabled:opacity-30"
              >
                <SkipForward className="h-4 w-4" />
              </button>
              <input
                type="range"
                min={0}
                max={timeline.length}
                value={cursor}
                onChange={(e) => seek(Number(e.target.value))}
                className="mx-2 flex-1"
              />
              <span className="w-20 shrink-0 text-right text-[11px] text-mission-muted">
                {cursor} / {timeline.length}
              </span>
              <div className="flex gap-1">
                {SPEEDS.map((s) => (
                  <button
                    key={s}
                    onClick={() => setSpeed(s)}
                    className={`rounded px-1.5 py-0.5 text-[10px] font-display ${
                      speed === s ? "bg-mission-accent/10 text-mission-accent" : "text-mission-muted"
                    }`}
                  >
                    {s}x
                  </button>
                ))}
              </div>
            </div>
            {latestEvent && (
              <p className="text-[11px] text-mission-muted">
                Last applied: <span className="text-slate-300">{latestEvent.type}</span> at{" "}
                {new Date(latestEvent.timestamp).toLocaleTimeString()}
              </p>
            )}
          </div>
        )}
      </GlassPanel>

      {reviewId && (
        <>
          <div className="grid h-[calc(100vh-420px)] min-h-[420px] grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
            <AgentGraphView
              hooks={replayStoreHooks}
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
              <AgentInspectorPanel agentId={selectedAgent} hooks={replayStoreHooks} />
              <ConditionInspectorPanel edgeId={selectedEdge} hooks={replayStoreHooks} />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[2fr_1fr]">
            <FindingsPage hooks={replayStoreHooks} />
            <TokenDashboard hooks={replayStoreHooks} />
          </div>
        </>
      )}
    </div>
  );
}
