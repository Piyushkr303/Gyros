import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { useReviewStore } from "../../store/reviewStore";
import type { EventType } from "../../types/domain";

export function TracesPage() {
  const events = useReviewStore((s) => s.events);
  const [typeFilter, setTypeFilter] = useState<EventType | "ALL">("ALL");
  const [expanded, setExpanded] = useState<string | null>(null);

  const types = useMemo(() => {
    const set = new Set<EventType>(events.map((e) => e.type));
    return Array.from(set).sort();
  }, [events]);

  const filtered = useMemo(
    () => [...events].reverse().filter((e) => typeFilter === "ALL" || e.type === typeFilter),
    [events, typeFilter],
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="mono-label">Event Type</span>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as EventType | "ALL")}
          className="rounded border border-mission-border bg-mission-panel px-2 py-1 text-xs text-slate-200"
        >
          <option value="ALL">ALL</option>
          {types.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <span className="ml-auto text-xs text-mission-muted">{filtered.length} / {events.length} event(s)</span>
      </div>

      <div className="glass-panel divide-y divide-mission-border/60 p-0">
        {filtered.length === 0 && <p className="p-4 text-xs text-mission-muted">No events recorded yet.</p>}
        {filtered.map((e) => {
          const isOpen = expanded === e.id;
          return (
            <div key={e.id} className="p-2.5">
              <button
                onClick={() => setExpanded(isOpen ? null : e.id)}
                className="flex w-full items-center gap-2 text-left text-xs"
              >
                {isOpen ? (
                  <ChevronDown className="h-3.5 w-3.5 shrink-0 text-mission-muted" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5 shrink-0 text-mission-muted" />
                )}
                <span className="text-mission-muted">{new Date(e.timestamp).toLocaleTimeString()}</span>
                <span className="font-display text-slate-200">{e.type}</span>
              </button>
              {isOpen && (
                <pre className="mt-2 max-h-64 overflow-auto rounded bg-mission-bg/60 p-2 text-[11px] text-slate-300">
                  {JSON.stringify(e.payload, null, 2)}
                </pre>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
