import type { ReactNode } from "react";

import { cn } from "../../lib/cn";

export function Badge({
  children,
  className,
  tone = "neutral",
}: {
  children: ReactNode;
  className?: string;
  tone?: "neutral" | "accent" | "success" | "warn" | "danger";
}) {
  const tones: Record<string, string> = {
    neutral: "bg-surface-2 text-muted border-border",
    accent: "bg-accent/10 text-accent border-accent/30",
    success: "bg-done/10 text-done border-done/30",
    warn: "bg-awaiting/10 text-awaiting border-awaiting/30",
    danger: "bg-failed/10 text-failed border-failed/30",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] font-medium leading-none",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
