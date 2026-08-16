interface Props {
  label: string;
  value: string | number;
  accent?: "accent" | "danger" | "warn" | "ok" | "muted";
}

const accentClass: Record<NonNullable<Props["accent"]>, string> = {
  accent: "text-mission-accent",
  danger: "text-mission-danger",
  warn: "text-mission-warn",
  ok: "text-mission-ok",
  muted: "text-slate-200",
};

export function StatTile({ label, value, accent = "muted" }: Props) {
  return (
    <div className="glass-panel px-4 py-3">
      <div className="mono-label">{label}</div>
      <div className={`mt-1 font-display text-2xl font-semibold ${accentClass[accent]}`}>{value}</div>
    </div>
  );
}
