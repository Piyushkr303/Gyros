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

const STATUS_STYLE: Record<AgentStatus, { border: string; glow: string; icon: JSX.Element }> = {
  IDLE: { border: "border-mission-border", glow: "", icon: <CircleDashed className="h-4 w-4 text-mission-muted" /> },
  QUEUED: { border: "border-mission-border", glow: "", icon: <CircleDashed className="h-4 w-4 text-mission-muted" /> },
  RUNNING: {
    border: "border-mission-accent2",
    glow: "shadow-[0_0_20px_rgba(129,140,248,0.35)]",
    icon: <Loader2 className="h-4 w-4 animate-spin text-mission-accent2" />,
  },
  THINKING_SUMMARY: {
    border: "border-mission-accent2",
    glow: "shadow-[0_0_20px_rgba(129,140,248,0.35)]",
    icon: <Loader2 className="h-4 w-4 animate-spin text-mission-accent2" />,
  },
  CALLING_TOOL: {
    border: "border-mission-accent",
    glow: "shadow-glow",
    icon: <Wrench className="h-4 w-4 animate-pulse text-mission-accent" />,
  },
  WAITING: { border: "border-mission-warn", glow: "", icon: <CircleDashed className="h-4 w-4 text-mission-warn" /> },
  COMMUNICATING: { border: "border-mission-accent2", glow: "shadow-glow", icon: <Loader2 className="h-4 w-4 animate-spin text-mission-accent2" /> },
  VALIDATING: { border: "border-mission-accent2", glow: "shadow-glow", icon: <Loader2 className="h-4 w-4 animate-spin text-mission-accent2" /> },
  FAILED: { border: "border-mission-danger", glow: "shadow-[0_0_20px_rgba(248,113,113,0.35)]", icon: <XCircle className="h-4 w-4 text-mission-danger" /> },
  COMPLETED: { border: "border-mission-ok", glow: "shadow-[0_0_16px_rgba(74,222,128,0.25)]", icon: <CheckCircle2 className="h-4 w-4 text-mission-ok" /> },
  SKIPPED: { border: "border-mission-border opacity-50", glow: "", icon: <CircleDashed className="h-4 w-4 text-mission-muted" /> },
};

export function AgentNode({ data }: NodeProps<AgentNodeData>) {
  const style = STATUS_STYLE[data.status] ?? STATUS_STYLE.IDLE;

  return (
    <motion.div
      initial={{ scale: 0.95, opacity: 0 }}
      animate={{ scale: 1, opacity: data.status === "SKIPPED" ? 0.5 : 1 }}
      transition={{ duration: 0.25 }}
      className={`glass-panel min-w-[170px] border-2 px-3 py-2 ${style.border} ${style.glow}`}
    >
      <Handle type="target" position={Position.Top} className="!bg-mission-border" />
      <div className="flex items-center gap-2">
        <Bot className="h-4 w-4 text-mission-accent" />
        <span className="font-display text-xs font-semibold text-slate-100">{data.label}</span>
        {data.dynamicallyActivated && (
          <Zap className="h-3 w-3 shrink-0 text-mission-warn" aria-label="Dynamically activated" />
        )}
      </div>
      <div className="mt-1.5 flex items-center justify-between">
        <span className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-mission-muted">
          {style.icon}
          {data.status}
        </span>
        {data.findingsCount > 0 && (
          <span className="rounded-full bg-mission-danger/20 px-1.5 text-[10px] text-mission-danger">
            {data.findingsCount}
          </span>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-mission-border" />
    </motion.div>
  );
}
