import type { Finding } from "../../types/domain";
import { Badge, incrementalStatusTone, severityTone } from "../common/Badge";

interface Props {
  finding: Finding;
  onOpenInExplorer?: (file: string, line: number | null) => void;
}

export function FindingCard({ finding, onOpenInExplorer }: Props) {
  return (
    <div className="glass-panel space-y-2 p-3">
      <div className="flex items-center gap-2">
        <Badge tone={severityTone(finding.severity)}>{finding.severity}</Badge>
        <Badge tone="info">{finding.category}</Badge>
        {finding.incremental_status && (
          <Badge tone={incrementalStatusTone(finding.incremental_status)}>{finding.incremental_status}</Badge>
        )}
        <span className="ml-auto text-[10px] text-mission-muted">{Math.round(finding.confidence * 100)}%</span>
      </div>
      <h4 className="text-sm font-semibold text-slate-100">{finding.title}</h4>
      <button
        onClick={() => onOpenInExplorer?.(finding.file, finding.line)}
        disabled={!onOpenInExplorer}
        className="text-left text-xs text-mission-muted enabled:hover:text-mission-accent enabled:hover:underline"
      >
        {finding.file}
        {finding.line ? `:${finding.line}` : ""}
      </button>
      <p className="text-xs text-slate-300">{finding.description}</p>
      {finding.recommendation && (
        <p className="text-xs text-mission-accent">→ {finding.recommendation}</p>
      )}
      {finding.debate_resolution && (
        <div className="rounded border border-mission-border bg-mission-bg/60 p-2 text-xs text-mission-muted">
          ⚖️ Debated: {finding.debate_resolution}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-1.5 border-t border-mission-border pt-2">
        <span className="text-[10px] text-mission-muted">Detected: {finding.detecting_agent}</span>
        <Badge tone={finding.validator_status === "CONFIRMED" ? "ok" : finding.validator_status === "REJECTED" ? "danger" : "warn"}>
          {finding.validator_status}
        </Badge>
        <Badge tone={finding.critic_status === "ACCEPTED" ? "ok" : "muted"}>{finding.critic_status}</Badge>
      </div>
    </div>
  );
}
