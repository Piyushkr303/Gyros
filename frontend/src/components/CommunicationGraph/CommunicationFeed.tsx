import { ArrowRight } from "lucide-react";

import { useReviewStore } from "../../store/reviewStore";
import { GlassPanel } from "../common/GlassPanel";

export function CommunicationFeed() {
  const messages = useReviewStore((s) => s.messages);

  return (
    <GlassPanel title="Agent Communication" subtitle={`${messages.length} message(s)`}>
      <div className="max-h-64 space-y-2 overflow-y-auto">
        {messages.length === 0 && <p className="text-xs text-mission-muted">No agent-to-agent messages yet.</p>}
        {[...messages].reverse().map((m) => (
          <div key={m.message_id} className="text-xs">
            <div className="flex items-center gap-1.5 text-slate-300">
              <span>{m.sender}</span>
              <ArrowRight className="h-3 w-3 text-mission-muted" />
              <span>{m.receiver}</span>
              <span className="ml-auto text-[10px] text-mission-muted">{m.type}</span>
            </div>
            <p className="text-mission-muted">{m.summary}</p>
          </div>
        ))}
      </div>
    </GlassPanel>
  );
}
