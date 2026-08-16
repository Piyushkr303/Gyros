import { useMemo, useState } from "react";

import { StatTile } from "../../components/common/StatTile";
import { ValidationPanel } from "../../components/ValidationPanel/ValidationPanel";
import { useReviewStore } from "../../store/reviewStore";
import type { ValidationStatus } from "../../types/domain";

const STATUSES: Array<ValidationStatus | "ALL"> = ["ALL", "CONFIRMED", "UNCERTAIN", "REJECTED", "PENDING"];

export function ValidationPage() {
  const findings = useReviewStore((s) => s.findings);
  const [status, setStatus] = useState<ValidationStatus | "ALL">("ALL");

  const { list, stats } = useMemo(() => {
    const all = Object.values(findings);
    const confirmed = all.filter((f) => f.validator_status === "CONFIRMED").length;
    const rejected = all.filter((f) => f.validator_status === "REJECTED").length;
    const uncertain = all.filter((f) => f.validator_status === "UNCERTAIN").length;
    const accepted = all.filter((f) => f.critic_status === "ACCEPTED").length;
    const weak = all.filter((f) => f.critic_status === "WEAK_EVIDENCE").length;
    const reanalyzed = all.filter((f) => f.reanalysis_count > 0).length;
    const filtered = all
      .filter((f) => status === "ALL" || f.validator_status === status)
      .sort((a, b) => b.confidence - a.confidence);
    return { list: filtered, stats: { confirmed, rejected, uncertain, accepted, weak, reanalyzed } };
  }, [findings, status]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatTile label="Confirmed" value={stats.confirmed} accent="ok" />
        <StatTile label="Uncertain" value={stats.uncertain} accent="warn" />
        <StatTile label="Rejected" value={stats.rejected} accent="danger" />
        <StatTile label="Critic Accepted" value={stats.accepted} accent="ok" />
        <StatTile label="Weak Evidence" value={stats.weak} accent="warn" />
        <StatTile label="Re-analyzed" value={stats.reanalyzed} />
      </div>

      <div className="flex items-center gap-2">
        <span className="mono-label">Filter</span>
        <div className="flex gap-1">
          {STATUSES.map((opt) => (
            <button
              key={opt}
              onClick={() => setStatus(opt)}
              className={`rounded-full border px-2 py-0.5 text-[10px] font-display uppercase tracking-wide transition-colors ${
                status === opt
                  ? "border-mission-accent bg-mission-accent/10 text-mission-accent"
                  : "border-mission-border text-mission-muted hover:text-slate-200"
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
        <span className="ml-auto text-xs text-mission-muted">{list.length} finding(s)</span>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {list.map((f) => (
          <ValidationPanel key={f.id} finding={f} />
        ))}
        {list.length === 0 && <p className="text-xs text-mission-muted">No findings match the current filter.</p>}
      </div>
    </div>
  );
}
