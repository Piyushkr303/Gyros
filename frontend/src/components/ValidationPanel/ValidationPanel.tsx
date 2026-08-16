import type { Finding } from "../../types/domain";
import { Badge } from "../common/Badge";

export function ValidationPanel({ finding }: { finding: Finding }) {
  const finalStatus =
    finding.validator_status === "CONFIRMED" && finding.critic_status === "ACCEPTED"
      ? "CONFIRMED"
      : finding.validator_status === "REJECTED" || finding.critic_status === "FALSE_POSITIVE"
        ? "REJECTED"
        : "PENDING";

  return (
    <div className="glass-panel space-y-3 p-4">
      <div className="mono-label">Finding {finding.id}</div>
      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        <div className="rounded border border-mission-border p-2">
          <div className="text-[10px] text-mission-muted">Detection</div>
          <div className="mt-1 text-slate-200">{finding.detecting_agent}</div>
        </div>
        <div className="rounded border border-mission-border p-2">
          <div className="text-[10px] text-mission-muted">Validation</div>
          <Badge tone={finding.validator_status === "CONFIRMED" ? "ok" : "warn"}>{finding.validator_status}</Badge>
        </div>
        <div className="rounded border border-mission-border p-2">
          <div className="text-[10px] text-mission-muted">Criticism</div>
          <Badge tone={finding.critic_status === "ACCEPTED" ? "ok" : "warn"}>{finding.critic_status}</Badge>
        </div>
      </div>
      <div className="flex items-center justify-between border-t border-mission-border pt-2 text-xs">
        <span className="text-mission-muted">Final Status</span>
        <Badge tone={finalStatus === "CONFIRMED" ? "ok" : finalStatus === "REJECTED" ? "danger" : "muted"}>
          {finalStatus}
        </Badge>
      </div>
      {finding.critic_notes && <p className="text-xs text-mission-muted">{finding.critic_notes}</p>}
    </div>
  );
}
