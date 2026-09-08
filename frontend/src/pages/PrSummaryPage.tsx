import { Link, useParams } from "react-router-dom";

import { usePr } from "../hooks/api/useTaskStages";
import { useCreatePr } from "../hooks/api/useTaskMutations";
import { useTask } from "../hooks/api/useTasks";
import { EmptyState } from "../components/feedback/EmptyState";
import { LoadingBlock } from "../components/feedback/LoadingBlock";
import { ErrorEnvelopeAlert } from "../components/feedback/ErrorEnvelopeAlert";
import { isStageNotReady } from "../services/errorMessages";
import { Badge } from "../components/primitives/Badge";
import { Button } from "../components/primitives/Button";
import { Card, CardBody, CardHeader } from "../components/primitives/Card";
import { absoluteTime } from "../lib/format";

export function PrSummaryPage() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  const pr = usePr(taskId);
  const create = useCreatePr(taskId);

  const verified = task.data?.state === "COMPLETED";

  if (pr.isLoading) return <LoadingBlock rows={4} />;

  if (pr.isError && isStageNotReady(pr.error)) {
    return (
      <EmptyState
        title="No pull request for this task"
        hint={
          verified
            ? "This task is complete — you can open a PR (needs an approver API key)."
            : "A PR can only be opened once the task is VERIFIED / COMPLETED."
        }
        action={
          verified ? (
            <Button
              size="sm"
              onClick={() => create.mutate(undefined)}
              disabled={create.isPending}
            >
              {create.isPending ? "Opening…" : "Open PR"}
            </Button>
          ) : undefined
        }
      />
    );
  }
  if (pr.isError) return <ErrorEnvelopeAlert error={pr.error} />;
  if (!pr.data) return null;

  const p = pr.data;

  return (
    <div className="space-y-4">
      {create.isError ? <ErrorEnvelopeAlert error={create.error} /> : null}
      <Card>
        <CardHeader
          title={p.title}
          subtitle={`${p.mode} · ${absoluteTime(p.created_at)}`}
          actions={<Badge tone={p.state === "FAILED" ? "danger" : "neutral"}>{p.state}</Badge>}
        />
        <CardBody className="space-y-2 text-sm">
          <div className="flex flex-wrap gap-2 text-xs">
            {p.branch ? <Badge tone="neutral">branch {p.branch}</Badge> : null}
            {p.commit_sha ? <Badge tone="neutral">{p.commit_sha.slice(0, 10)}</Badge> : null}
            {p.github_number ? <Badge tone="neutral">#{p.github_number}</Badge> : null}
          </div>
          {p.github_url ? (
            <a
              href={p.github_url}
              target="_blank"
              rel="noreferrer"
              className="text-accent underline"
            >
              Open on GitHub ↗
            </a>
          ) : null}
          {p.failure_reason ? (
            <p className="rounded border border-failed/30 bg-failed/10 p-2 text-xs text-failed">
              {p.failure_reason}
            </p>
          ) : null}
          <p className="text-xs text-muted">Body artifact: {p.body_artifact_id}</p>
          <Link to={`/tasks/${taskId}/changes`} className="text-xs text-accent underline">
            View the patch →
          </Link>
        </CardBody>
      </Card>
    </div>
  );
}
