import type { ReactNode } from "react";

import { cn } from "../../lib/cn";

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  );
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead className="text-left text-xs uppercase tracking-wide text-muted">{children}</thead>
  );
}

export function TR({ children, className }: { children: ReactNode; className?: string }) {
  return <tr className={cn("border-b border-border last:border-0", className)}>{children}</tr>;
}

export function TH({ children, className }: { children: ReactNode; className?: string }) {
  return <th className={cn("px-2 py-2 font-medium", className)}>{children}</th>;
}

export function TD({ children, className }: { children: ReactNode; className?: string }) {
  return <td className={cn("px-2 py-2 align-top", className)}>{children}</td>;
}
