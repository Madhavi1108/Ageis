import { ClassificationBadge } from "../state/badges";

export function ScoreDial({
  label,
  value,
  classification,
  confidence,
}: {
  label: string;
  value: number;
  classification: string;
  confidence?: number;
}) {
  return (
    <div className="rounded-md border border-border bg-surface-2 px-3 py-2">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs text-muted">{label}</span>
        <ClassificationBadge value={classification} />
      </div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {confidence != null ? (
        <div className="text-[11px] text-muted">confidence {(confidence * 100).toFixed(0)}%</div>
      ) : null}
    </div>
  );
}
