import type { PropsWithChildren } from "react";

interface Props {
  className?: string;
  title?: string;
  subtitle?: string;
}

export function GlassPanel({ className = "", title, subtitle, children }: PropsWithChildren<Props>) {
  return (
    <div className={`glass-panel p-4 ${className}`}>
      {title && (
        <div className="mb-3 flex items-baseline justify-between">
          <h3 className="mono-label">{title}</h3>
          {subtitle && <span className="text-[11px] text-mission-muted">{subtitle}</span>}
        </div>
      )}
      {children}
    </div>
  );
}
