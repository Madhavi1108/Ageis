import { NavLink, Outlet, useParams } from "react-router-dom";

import { useTask } from "../hooks/api/useTasks";
import { LoadingBlock } from "../components/feedback/LoadingBlock";
import { QueryError } from "../components/feedback/QueryError";
import { TaskStateBadge } from "../components/state/badges";
import { cn } from "../lib/cn";

const TABS = [
  { to: "", label: "Pipeline", end: true },
  { to: "plan", label: "Plan" },
  { to: "impact", label: "Impact" },
  { to: "changes", label: "Diff" },
  { to: "tests", label: "Tests" },
  { to: "debugging", label: "Debugging" },
  { to: "review", label: "Review" },
  { to: "verification", label: "Verification" },
  { to: "pr", label: "PR" },
];

export function TaskLayout() {
  const { taskId } = useParams();
  const task = useTask(taskId);

  return (
    <div className="space-y-4">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-lg font-semibold">
            {task.data?.title ?? "Task"}
          </h1>
          {task.data ? <TaskStateBadge state={task.data.state} /> : null}
        </div>
        {task.data ? (
          <p className="mt-0.5 text-xs text-muted">
            {task.data.task_type} · {task.data.priority} · repo {task.data.repository_id} · id{" "}
            {task.data.id}
          </p>
        ) : null}
      </div>

      <nav className="flex flex-wrap gap-1 border-b border-border">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            className={({ isActive }) =>
              cn(
                "px-3 py-1.5 text-sm",
                isActive
                  ? "border-b-2 border-accent font-medium text-fg"
                  : "text-muted hover:text-fg",
              )
            }
          >
            {t.label}
          </NavLink>
        ))}
      </nav>

      {task.isLoading ? (
        <LoadingBlock rows={4} />
      ) : task.isError ? (
        <QueryError error={task.error} onRetry={() => task.refetch()} />
      ) : (
        <Outlet />
      )}
    </div>
  );
}
