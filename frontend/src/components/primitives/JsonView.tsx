import { useState } from "react";

import { cn } from "../../lib/cn";

export function JsonView({
  value,
  collapsed = true,
  label = "details",
  className,
}: {
  value: unknown;
  collapsed?: boolean;
  label?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(!collapsed);
  if (value == null) return null;
  const text = JSON.stringify(value, null, 2);
  return (
    <div className={cn("text-xs", className)}>
      <button
        type="button"
        className="text-accent underline decoration-dotted"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        {open ? `Hide ${label}` : `Show ${label}`}
      </button>
      {open ? (
        <pre className="mt-1 max-h-64 overflow-auto rounded bg-surface-2 p-2 font-mono">
          {text}
        </pre>
      ) : null}
    </div>
  );
}
