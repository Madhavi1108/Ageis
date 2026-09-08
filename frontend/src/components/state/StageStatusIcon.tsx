import type { StageStatus } from "../../types/pipeline";

const MAP: Record<StageStatus, { glyph: string; className: string; label: string }> = {
  done: { glyph: "●", className: "text-done", label: "done" },
  active: { glyph: "◐", className: "text-active animate-pulse", label: "in progress" },
  failed: { glyph: "✕", className: "text-failed", label: "failed" },
  skipped: { glyph: "○", className: "text-skipped", label: "skipped" },
  pending: { glyph: "○", className: "text-pending", label: "pending" },
};

export function StageStatusIcon({ status }: { status: StageStatus }) {
  const m = MAP[status];
  return (
    <span className={`inline-block w-4 text-center ${m.className}`} title={m.label} aria-label={m.label}>
      {m.glyph}
    </span>
  );
}
