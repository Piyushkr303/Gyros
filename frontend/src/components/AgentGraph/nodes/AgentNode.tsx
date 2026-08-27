import { Handle, Position, type NodeProps } from "reactflow";
import { motion } from "framer-motion";
import { Bot, CheckCircle2, CircleDashed, Loader2, Wrench, XCircle, Zap } from "lucide-react";

import type { AgentStatus } from "../../../types/domain";

export interface AgentNodeData {
  label: string;
  status: AgentStatus;
  findingsCount: number;
  dynamicallyActivated?: boolean;
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

export function AgentNode({ data }: NodeProps<AgentNodeData>) {
  const meta = STATUS_META[data.status] ?? STATUS_META.IDLE;
  const isSkipped = data.status === "SKIPPED";

  return (
    <div className="relative">
      {meta.pulse && (
        <motion.div
          className="pointer-events-none absolute -inset-1.5 rounded-2xl"
          style={{ border: `1.5px solid ${meta.color}` }}
          animate={{ opacity: [0.5, 0, 0.5], scale: [1, 1.1, 1] }}
          transition={{ duration: 2.6, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: isSkipped ? 0.5 : 1 }}
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
        </div>

        <Handle type="source" position={Position.Bottom} className="!h-2 !w-2 !border-0" style={{ background: meta.color }} />
      </motion.div>
    </div>
  );
}
