import { useMemo, useState } from "react";

import { FindingCard } from "../../components/FindingCard/FindingCard";
import { liveStoreHooks, type ReducerStoreHooks } from "../../store/storeHooks";
import type { Severity, ValidationStatus } from "../../types/domain";

const SEVERITIES: Array<Severity | "ALL"> = ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"];
const STATUSES: Array<ValidationStatus | "ALL"> = ["ALL", "CONFIRMED", "UNCERTAIN", "REJECTED", "PENDING"];

interface Props {
  onOpenInExplorer?: (file: string, line: number | null) => void;
  hooks?: ReducerStoreHooks;
}

export function FindingsPage({ onOpenInExplorer, hooks = liveStoreHooks }: Props) {
  const findings = hooks.useFindings();
  const [severity, setSeverity] = useState<Severity | "ALL">("ALL");
  const [status, setStatus] = useState<ValidationStatus | "ALL">("ALL");

  const filtered = useMemo(() => {
    return Object.values(findings)
      .filter((f) => severity === "ALL" || f.severity === severity)
      .filter((f) => status === "ALL" || f.validator_status === status)
      .sort((a, b) => b.confidence - a.confidence);
  }, [findings, severity, status]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <FilterGroup label="Severity" options={SEVERITIES} value={severity} onChange={setSeverity} />
        <FilterGroup label="Validation" options={STATUSES} value={status} onChange={setStatus} />
        <span className="ml-auto text-xs text-mission-muted">{filtered.length} finding(s)</span>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((f) => (
          <FindingCard key={f.id} finding={f} onOpenInExplorer={onOpenInExplorer} />
        ))}
        {filtered.length === 0 && <p className="text-xs text-mission-muted">No findings match the current filters.</p>}
      </div>
    </div>
  );
}

function FilterGroup<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: T[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="mono-label">{label}</span>
      <div className="flex gap-1">
        {options.map((opt) => (
          <button
            key={opt}
            onClick={() => onChange(opt)}
            className={`rounded-full border px-2 py-0.5 text-[10px] font-display uppercase tracking-wide transition-colors ${
              value === opt
                ? "border-mission-accent bg-mission-accent/10 text-mission-accent"
                : "border-mission-border text-mission-muted hover:text-slate-200"
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  );
}
