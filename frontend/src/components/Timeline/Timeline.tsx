import { useReviewStore } from "../../store/reviewStore";
import { GlassPanel } from "../common/GlassPanel";

function eventColor(type: string): string {
  if (type.includes("FAILED") || type.includes("REJECTED")) return "text-mission-danger";
  if (type.includes("COMPLETED") || type.includes("CONFIRMED") || type.includes("VALIDATED")) return "text-mission-ok";
  if (type.includes("SKIPPED")) return "text-mission-muted";
  if (type.includes("CONFLICT")) return "text-mission-warn";
  if (type.includes("TRIGGERED") || type.includes("STARTED")) return "text-mission-accent2";
  return "text-slate-300";
}

export function Timeline() {
  const events = useReviewStore((s) => s.events);

  return (
    <GlassPanel title="Execution Timeline" subtitle={`${events.length} event(s)`}>
      <div className="max-h-80 space-y-1 overflow-y-auto font-display text-[11px]">
        {[...events].reverse().map((e) => (
          <div key={e.id} className="flex items-start gap-2">
            <span className="text-mission-muted">{new Date(e.timestamp).toLocaleTimeString()}</span>
            <span className={eventColor(e.type)}>{e.type}</span>
          </div>
        ))}
      </div>
    </GlassPanel>
  );
}
