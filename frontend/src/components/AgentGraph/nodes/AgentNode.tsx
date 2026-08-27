import { Handle, Position, type NodeProps } from "reactflow";
import { motion } from "framer-motion";
import { Bot, CheckCircle2, CircleDashed, Loader2, Wrench, XCircle, Zap } from "lucide-react";

import type { AgentStatus } from "../../../types/domain";

export interface AgentNodeData {
  label: string;
  status: AgentStatus;
  findingsCount: number;
  dynamicallyActivated?: boolean;
  /** ms since this agent entered its current processing streak - only set
   * for agents actively running, so the card can show a live "how long has
   * this taken" readout instead of just a spinner. */
  elapsedMs?: number;
  /** True when no non-skipped/non-failed path from an entry node reaches
   * this node yet - it's sitting on a branch that's effectively dead, so it
   * fades out of the way instead of competing visually with the live path. */
  dimmed?: boolean;
  /** Compact mode: render as an icon-only chip: label/status appear in a
   * hover tooltip instead of taking up card space, so a large graph fits in
   * view without zooming out to illegibility. */
  compact?: boolean;
}

export interface StatusMeta {
  color: string;
  label: string;
  icon: (className: string) => JSX.Element;
  /** Actively working right now - gets the pulsing focus ring + glow. */
  pulse: boolean;
}

// Single source of truth for status -> color/icon, shared by the node card
// and the graph legend so they can never drift out of sync.
export const STATUS_META: Record<AgentStatus, StatusMeta> = {
  IDLE: { color: "#475569", label: "Idle", pulse: false, icon: (c) => <CircleDashed className={c} /> },
  QUEUED: { color: "#475569", label: "Queued", pulse: false, icon: (c) => <CircleDashed className={c} /> },
  RUNNING: { color: "#818cf8", label: "Running", pulse: true, icon: (c) => <Loader2 className={`${c} animate-spin`} /> },
  THINKING_SUMMARY: {
    color: "#818cf8",
    label: "Thinking",
    pulse: true,
    icon: (c) => <Loader2 className={`${c} animate-spin`} />,
  },
  CALLING_TOOL: { color: "#5eead4", label: "Calling tool", pulse: true, icon: (c) => <Wrench className={`${c} animate-pulse`} /> },
  WAITING: { color: "#fbbf24", label: "Waiting", pulse: false, icon: (c) => <CircleDashed className={c} /> },
  COMMUNICATING: {
    color: "#818cf8",
    label: "Communicating",
    pulse: true,
    icon: (c) => <Loader2 className={`${c} animate-spin`} />,
  },
  VALIDATING: { color: "#818cf8", label: "Validating", pulse: true, icon: (c) => <Loader2 className={`${c} animate-spin`} /> },
  FAILED: { color: "#f87171", label: "Failed", pulse: false, icon: (c) => <XCircle className={c} /> },
  COMPLETED: { color: "#4ade80", label: "Completed", pulse: false, icon: (c) => <CheckCircle2 className={c} /> },
  SKIPPED: { color: "#334155", label: "Skipped", pulse: false, icon: (c) => <CircleDashed className={c} /> },
};

function formatElapsed(ms: number): string {
  const totalSeconds = ms / 1000;
  if (totalSeconds < 60) return `${totalSeconds.toFixed(1)}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.floor(totalSeconds % 60);
  return `${minutes}m ${seconds}s`;
}

export function AgentNode({ data }: NodeProps<AgentNodeData>) {
  const meta = STATUS_META[data.status] ?? STATUS_META.IDLE;
  const isSkipped = data.status === "SKIPPED";
  const cardOpacity = isSkipped ? 0.5 : data.dimmed ? 0.35 : 1;

  const pulseRing = meta.pulse && (
    <motion.div
      className="pointer-events-none absolute -inset-1.5 rounded-2xl"
      style={{ border: `1.5px solid ${meta.color}` }}
      animate={{ opacity: [0.5, 0, 0.5], scale: [1, 1.1, 1] }}
      transition={{ duration: 2.6, repeat: Infinity, ease: "easeInOut" }}
    />
  );

  if (data.compact) {
    return (
      <div className="group relative">
        {pulseRing}
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: cardOpacity }}
          whileHover={{ scale: 1.08 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
          style={{ borderColor: meta.color, boxShadow: meta.pulse ? `0 0 18px ${meta.color}40` : "none" }}
          className="glass-panel relative flex h-14 w-14 cursor-pointer select-none items-center justify-center rounded-2xl border-2 transition-[border-color,box-shadow] duration-500 ease-out"
        >
          <Handle type="target" position={Position.Top} className="!h-2 !w-2 !border-0" style={{ background: meta.color }} />
          {data.findingsCount > 0 && (
            <span className="absolute -right-1.5 -top-1.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-mission-danger px-1 text-[9px] font-semibold text-mission-bg ring-2 ring-mission-bg">
              {data.findingsCount}
            </span>
          )}
          <Bot className="h-4 w-4" style={{ color: meta.color }} />
          <span
            className="absolute -bottom-1 -right-1 h-2.5 w-2.5 rounded-full ring-2 ring-mission-bg"
            style={{ backgroundColor: meta.color }}
          />
          <Handle type="source" position={Position.Bottom} className="!h-2 !w-2 !border-0" style={{ background: meta.color }} />
        </motion.div>

        {/* Hover tooltip carries the label/status/elapsed that compact mode hides from the card itself. */}
        <div className="pointer-events-none absolute left-1/2 top-full z-10 mt-2 w-max max-w-[200px] -translate-x-1/2 rounded-lg border border-mission-border bg-mission-panel px-2.5 py-1.5 opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100">
          <div className="font-display text-[11px] font-semibold capitalize text-slate-100">{data.label}</div>
          <div className="mt-0.5 flex items-center gap-1.5 text-[9px] uppercase tracking-wide" style={{ color: meta.color }}>
            {meta.icon("h-2.5 w-2.5")}
            {meta.label}
            {data.elapsedMs != null && <span className="text-mission-muted">· {formatElapsed(data.elapsedMs)}</span>}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative">
      {pulseRing}
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: cardOpacity }}
        whileHover={{ scale: 1.03 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        style={{
          borderColor: meta.color,
          boxShadow: meta.pulse
            ? `0 0 22px ${meta.color}40`
            : data.status === "COMPLETED"
              ? `0 0 14px ${meta.color}26`
              : "none",
        }}
        className="glass-panel relative min-w-[178px] cursor-pointer select-none rounded-2xl border-2 px-3.5 py-2.5 transition-[border-color,box-shadow] duration-500 ease-out"
      >
        <Handle type="target" position={Position.Top} className="!h-2 !w-2 !border-0" style={{ background: meta.color }} />

        {data.findingsCount > 0 && (
          <span className="absolute -right-2 -top-2 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-mission-danger px-1 text-[10px] font-semibold text-mission-bg ring-2 ring-mission-bg">
            {data.findingsCount}
          </span>
        )}

        <div className="flex items-center gap-2">
          <span
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg"
            style={{ backgroundColor: `${meta.color}1f` }}
          >
            <Bot className="h-3.5 w-3.5" style={{ color: meta.color }} />
          </span>
          <span className="truncate font-display text-xs font-semibold capitalize text-slate-100">{data.label}</span>
          {data.dynamicallyActivated && (
            <Zap className="h-3 w-3 shrink-0 text-mission-warn" aria-label="Dynamically activated" />
          )}
        </div>

        <div
          className="mt-2 flex w-fit items-center gap-1.5 rounded-full px-2 py-0.5 text-[9px] font-medium uppercase tracking-wide transition-colors duration-500 ease-out"
          style={{ backgroundColor: `${meta.color}1a`, color: meta.color }}
        >
          {meta.icon("h-3 w-3")}
          {meta.label}
          {data.elapsedMs != null && <span className="opacity-70">· {formatElapsed(data.elapsedMs)}</span>}
        </div>

        <Handle type="source" position={Position.Bottom} className="!h-2 !w-2 !border-0" style={{ background: meta.color }} />
      </motion.div>
    </div>
  );
}
