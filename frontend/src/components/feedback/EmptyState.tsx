import type { ReactNode } from "react";

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: ReactNode;
  hint?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-surface px-4 py-8 text-center">
      <p className="text-sm font-medium">{title}</p>
      {hint ? <p className="mx-auto mt-1 max-w-md text-xs text-muted">{hint}</p> : null}
      {action ? <div className="mt-3 flex justify-center">{action}</div> : null}
    </div>
  );
}
