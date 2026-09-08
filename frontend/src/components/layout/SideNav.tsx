import { NavLink } from "react-router-dom";

import { cn } from "../../lib/cn";

const GROUPS: { title: string; links: { to: string; label: string; end?: boolean }[] }[] = [
  {
    title: "Repositories",
    links: [
      { to: "/", label: "Dashboard", end: true },
      { to: "/tasks/new", label: "Create task" },
    ],
  },
  {
    title: "Tasks",
    links: [{ to: "/tasks", label: "All tasks", end: true }],
  },
  {
    title: "Knowledge",
    links: [{ to: "/memory", label: "Engineering memory" }],
  },
  {
    title: "System",
    links: [
      { to: "/settings", label: "Settings" },
      { to: "/health", label: "Health" },
    ],
  },
];

export function SideNav() {
  return (
    <nav aria-label="Primary" className="flex w-52 shrink-0 flex-col gap-4 border-r border-border bg-surface p-3">
      <div className="px-2 text-sm font-bold tracking-tight">AEGIS</div>
      {GROUPS.map((g) => (
        <div key={g.title}>
          <div className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">
            {g.title}
          </div>
          <ul className="space-y-0.5">
            {g.links.map((l) => (
              <li key={l.to}>
                <NavLink
                  to={l.to}
                  end={l.end}
                  className={({ isActive }) =>
                    cn(
                      "block rounded px-2 py-1.5 text-sm",
                      isActive ? "bg-accent/10 font-medium text-accent" : "text-fg hover:bg-surface-2",
                    )
                  }
                >
                  {l.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}
