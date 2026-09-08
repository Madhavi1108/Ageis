import * as RA from "@radix-ui/react-accordion";
import type { ReactNode } from "react";

import { cn } from "../../lib/cn";

export interface AccordionItemDef {
  value: string;
  header: ReactNode;
  body: ReactNode;
}

export function Accordion({
  items,
  value,
  onValueChange,
  type = "multiple",
}: {
  items: AccordionItemDef[];
  value?: string[];
  onValueChange?: (v: string[]) => void;
  type?: "multiple";
}) {
  return (
    <RA.Root
      type={type}
      value={value}
      onValueChange={onValueChange as (v: string[]) => void}
      className="divide-y divide-border rounded-lg border border-border bg-surface"
    >
      {items.map((it) => (
        <RA.Item key={it.value} value={it.value}>
          <RA.Header>
            <RA.Trigger
              className={cn(
                "flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left text-sm hover:bg-surface-2",
                "data-[state=open]:bg-surface-2",
              )}
            >
              {it.header}
              <span aria-hidden className="text-muted transition-transform data-[state=open]:rotate-180">
                ▾
              </span>
            </RA.Trigger>
          </RA.Header>
          <RA.Content className="px-3 pb-3 pt-1 text-sm">{it.body}</RA.Content>
        </RA.Item>
      ))}
    </RA.Root>
  );
}
