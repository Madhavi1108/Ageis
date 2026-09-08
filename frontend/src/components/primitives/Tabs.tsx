import * as RT from "@radix-ui/react-tabs";
import type { ReactNode } from "react";

import { cn } from "../../lib/cn";

export interface TabItem {
  value: string;
  label: ReactNode;
  content: ReactNode;
}

export function Tabs({
  items,
  value,
  onValueChange,
  defaultValue,
}: {
  items: TabItem[];
  value?: string;
  onValueChange?: (v: string) => void;
  defaultValue?: string;
}) {
  return (
    <RT.Root
      value={value}
      onValueChange={onValueChange}
      defaultValue={defaultValue ?? items[0]?.value}
    >
      <RT.List className="flex flex-wrap gap-1 border-b border-border">
        {items.map((it) => (
          <RT.Trigger
            key={it.value}
            value={it.value}
            className={cn(
              "px-3 py-1.5 text-sm text-muted data-[state=active]:border-b-2 data-[state=active]:border-accent data-[state=active]:text-fg",
            )}
          >
            {it.label}
          </RT.Trigger>
        ))}
      </RT.List>
      {items.map((it) => (
        <RT.Content key={it.value} value={it.value} className="pt-3 focus:outline-none">
          {it.content}
        </RT.Content>
      ))}
    </RT.Root>
  );
}
