import { cn } from "../../lib/cn";

export function LoadingBlock({ label = "Loading…", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div className="space-y-2" role="status" aria-live="polite" aria-busy="true">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className={cn("h-4 animate-pulse rounded bg-surface-2", i === 0 ? "w-2/3" : "w-full")}
        />
      ))}
    </div>
  );
}

export function InlineSpinner({ label = "Loading…" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-muted" role="status">
      <span className="h-3 w-3 animate-spin rounded-full border-2 border-border border-t-accent" />
      {label}
    </span>
  );
}
