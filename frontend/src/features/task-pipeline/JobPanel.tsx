import { useCancelJob } from "../../hooks/api/useJobs";
import type { JobView } from "../../types/api";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { TaskStateBadge } from "../../components/state/badges";
import { relativeTime } from "../../lib/format";

export function JobPanel({ jobs }: { jobs: JobView[] }) {
  const cancel = useCancelJob();
  if (!jobs.length) return null;
  const latest = jobs[0];
  const checkpoint = (latest.last_checkpoint as { stage?: string } | null)?.stage;

  return (
    <div className="rounded-md border border-border bg-surface-2 px-3 py-2 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">Job {latest.type}</span>
        <TaskStateBadge state={latest.state} />
        <Badge tone="neutral">
          attempt {latest.attempts}/{latest.max_attempts}
        </Badge>
        {checkpoint ? <Badge tone="neutral">checkpoint: {checkpoint}</Badge> : null}
        <span className="text-muted">queued {relativeTime(latest.queued_at)}</span>
        {latest.state === "RUNNING" || latest.state === "QUEUED" ? (
          <Button
            size="sm"
            variant="ghost"
            disabled={cancel.isPending}
            onClick={() => cancel.mutate(latest.id)}
          >
            Cancel job
          </Button>
        ) : null}
      </div>
      <div className="mt-1 h-1.5 w-full overflow-hidden rounded bg-border">
        <div
          className="h-full bg-accent transition-all"
          style={{ width: `${Math.round((latest.progress ?? 0) * 100)}%` }}
        />
      </div>
      {latest.error ? (
        <pre className="mt-1 overflow-x-auto rounded bg-surface p-1.5 text-failed">
          {JSON.stringify(latest.error, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}
