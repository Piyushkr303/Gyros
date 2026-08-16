import { useMemo, useState } from "react";
import { CheckCircle2, ShieldAlert, XCircle } from "lucide-react";

import { GlassPanel } from "../../components/common/GlassPanel";
import { Badge, severityTone } from "../../components/common/Badge";
import { api } from "../../services/api";
import { useReviewStore } from "../../store/reviewStore";

export function ApprovalPage() {
  const reviewId = useReviewStore((s) => s.reviewId);
  const approvalRequired = useReviewStore((s) => s.approvalRequired);
  const findings = useReviewStore((s) => s.findings);
  const [busy, setBusy] = useState(false);
  const [decision, setDecision] = useState<"APPROVE" | "REJECT" | null>(null);

  const publishable = useMemo(
    () => Object.values(findings).filter((f) => f.validator_status === "CONFIRMED" && f.critic_status === "ACCEPTED"),
    [findings]
  );
  const highSeverity = publishable.filter((f) => f.severity === "HIGH" || f.severity === "CRITICAL");

  async function act(action: "approve" | "reject") {
    if (!reviewId) return;
    setBusy(true);
    try {
      await (action === "approve" ? api.approve(reviewId) : api.reject(reviewId));
      setDecision(action === "approve" ? "APPROVE" : "REJECT");
    } finally {
      setBusy(false);
    }
  }

  if (!approvalRequired && !decision) {
    return (
      <GlassPanel title="Human Approval">
        <p className="text-xs text-mission-muted">
          No review is currently awaiting approval. This gate opens once Final Review completes.
        </p>
      </GlassPanel>
    );
  }

  return (
    <GlassPanel title="AI Recommendation">
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <ShieldAlert className={`h-5 w-5 ${highSeverity.length ? "text-mission-danger" : "text-mission-ok"}`} />
          <span className="font-display text-sm font-semibold">
            {highSeverity.length ? "REQUEST CHANGES" : "APPROVE"}
          </span>
        </div>

        <p className="text-xs text-mission-muted">
          {highSeverity.length} HIGH+ severity finding(s) out of {publishable.length} confirmed finding(s).
        </p>

        <div className="space-y-1.5">
          {publishable.map((f) => (
            <div key={f.id} className="flex items-center gap-2 text-xs">
              <Badge tone={severityTone(f.severity)}>{f.severity}</Badge>
              <span className="text-slate-300">{f.title}</span>
              <span className="ml-auto text-mission-muted">
                {f.file}
                {f.line ? `:${f.line}` : ""}
              </span>
            </div>
          ))}
        </div>

        {decision ? (
          <div className="flex items-center gap-2 border-t border-mission-border pt-3 text-xs">
            {decision === "APPROVE" ? (
              <CheckCircle2 className="h-4 w-4 text-mission-ok" />
            ) : (
              <XCircle className="h-4 w-4 text-mission-danger" />
            )}
            <span>Decision recorded: {decision}</span>
          </div>
        ) : (
          <div className="flex gap-2 border-t border-mission-border pt-3">
            <button
              disabled={busy}
              onClick={() => act("approve")}
              className="flex-1 rounded-lg border border-mission-ok/40 bg-mission-ok/10 px-3 py-2 text-xs font-display uppercase tracking-wide text-mission-ok transition hover:bg-mission-ok/20 disabled:opacity-50"
            >
              Approve
            </button>
            <button
              disabled={busy}
              onClick={() => act("reject")}
              className="flex-1 rounded-lg border border-mission-danger/40 bg-mission-danger/10 px-3 py-2 text-xs font-display uppercase tracking-wide text-mission-danger transition hover:bg-mission-danger/20 disabled:opacity-50"
            >
              Reject
            </button>
          </div>
        )}
      </div>
    </GlassPanel>
  );
}
