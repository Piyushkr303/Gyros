import type { PropsWithChildren } from "react";

type Tone = "accent" | "danger" | "warn" | "ok" | "muted" | "info";

const toneClass: Record<Tone, string> = {
  accent: "bg-mission-accent/10 text-mission-accent border-mission-accent/30",
  danger: "bg-mission-danger/10 text-mission-danger border-mission-danger/30",
  warn: "bg-mission-warn/10 text-mission-warn border-mission-warn/30",
  ok: "bg-mission-ok/10 text-mission-ok border-mission-ok/30",
  muted: "bg-mission-muted/10 text-mission-muted border-mission-muted/30",
  info: "bg-mission-accent2/10 text-mission-accent2 border-mission-accent2/30",
};

export function Badge({ tone = "muted", children }: PropsWithChildren<{ tone?: Tone }>) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-display uppercase tracking-wider ${toneClass[tone]}`}>
      {children}
    </span>
  );
}

export function severityTone(severity: string): Tone {
  switch (severity) {
    case "CRITICAL":
      return "danger";
    case "HIGH":
      return "danger";
    case "MEDIUM":
      return "warn";
    default:
      return "muted";
  }
}

export function incrementalStatusTone(status: string): Tone {
  switch (status) {
    case "NEW":
      return "accent";
    case "RESOLVED":
      return "ok";
    case "UNCHANGED":
      return "info";
    case "INVALIDATED":
      return "danger";
    default:
      return "muted"; // STALE
  }
}
