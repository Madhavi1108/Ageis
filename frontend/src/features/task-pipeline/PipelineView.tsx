import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useJobsForTask } from "../../hooks/api/useJobs";
import { useCancelTask, useRunTask, useTask, useTaskTimeline } from "../../hooks/api/useTasks";
import { qk } from "../../services/queryKeys";
import { QueryError } from "../../components/feedback/QueryError";
import { LoadingBlock } from "../../components/feedback/LoadingBlock";
import { Accordion, type AccordionItemDef } from "../../components/primitives/Accordion";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { Card, CardBody, CardHeader } from "../../components/primitives/Card";
import { StageStatusIcon } from "../../components/state/StageStatusIcon";
import { TaskStateBadge } from "../../components/state/badges";
import { duration } from "../../lib/format";
import { STAGES } from "../../types/pipeline";
import { computeStageViews, type StageView } from "./stageStatus";
import { JobPanel } from "./JobPanel";
import { StagePanelContent } from "./stagePanels";

export function PipelineView({
  taskId,
  forceOpenAll = false,
}: {
  taskId: string;
  forceOpenAll?: boolean;
}) {
  const qc = useQueryClient();
  const task = useTask(taskId);
  const timeline = useTaskTimeline(taskId, task.data?.state);
  const jobs = useJobsForTask(taskId, task.data?.state);
  const [openValues, setOpenValues] = useState<string[]>([]);

  const state = task.data?.state;
  useEffect(() => {
    if (!state) return;
    const def = STAGES.find((s) => s.state === state);
    if (def?.stageKey) {
      void qc.invalidateQueries({ queryKey: qk.taskStage(taskId, def.stageKey) });
    }
  }, [state, taskId, qc]);

  const views = useMemo<StageView[]>(() => {
    if (!task.data || !timeline.data) return [];
    return computeStageViews({
      taskState: task.data.state,
      terminalReason: task.data.terminal_reason,
      entries: timeline.data.entries,
    });
  }, [task.data, timeline.data]);

  if (task.isLoading) return <LoadingBlock rows={4} />;
  if (task.isError) return <QueryError error={task.error} onRetry={() => task.refetch()} />;
  if (!task.data) return null;

  const t = task.data;
  const allValues = views.map((v) => v.def.id);
  const effectiveOpen = forceOpenAll ? allValues : openValues;

  const items: AccordionItemDef[] = views.map((v) => ({
    value: v.def.id,
    header: (
      <span className="flex flex-1 items-center gap-2">
        <StageStatusIcon status={v.status} />
        <span className="font-medium">{v.def.label}</span>
        {v.attempts > 1 ? <Badge tone="neutral">{v.attempts}×</Badge> : null}
        {v.durationMs != null ? (
          <span className="text-xs text-muted">{duration(v.durationMs)}</span>
        ) : null}
        {v.note ? <span className="text-xs text-awaiting">{v.note}</span> : null}
      </span>
    ),
    body: (
      <div className="space-y-2">
        {v.error ? (
          <pre className="overflow-x-auto rounded bg-surface-2 p-2 text-xs text-failed">
            {JSON.stringify(v.error, null, 2)}
          </pre>
        ) : null}
        <StagePanelContent
          stageId={v.def.id}
          taskId={taskId}
          open={forceOpenAll || effectiveOpen.includes(v.def.id)}
        />
      </div>
    ),
  }));

  return (
    <div className="space-y-3">
      <Card>
        <CardHeader
          title={
            <span className="flex flex-wrap items-center gap-2">
              <TaskStateBadge state={t.state} />
              {t.terminal_reason ? (
                <span className="text-xs text-muted">{t.terminal_reason}</span>
              ) : null}
            </span>
          }
          actions={
            <PipelineActions taskId={taskId} state={t.state} />
          }
        />
        <CardBody className="space-y-2">
          {jobs.data?.items?.length ? <JobPanel jobs={jobs.data.items} /> : null}
          {timeline.isLoading ? <LoadingBlock rows={2} /> : null}
        </CardBody>
      </Card>

      {items.length ? (
        <Accordion items={items} value={effectiveOpen} onValueChange={setOpenValues} />
      ) : (
        <LoadingBlock rows={6} />
      )}
    </div>
  );
}

function PipelineActions({ taskId, state }: { taskId: string; state: string }) {
  const run = useRunTask(taskId);
  const cancel = useCancelTask(taskId);
  const terminal = ["COMPLETED", "FAILED", "CANCELLED", "PARTIALLY_SUPPORTED"].includes(state);
  return (
    <div className="flex items-center gap-2">
      <Button
        size="sm"
        variant="primary"
        disabled={run.isPending || (!terminal && state !== "PENDING")}
        onClick={() => run.mutate()}
      >
        {state === "PENDING" ? "Run" : "Re-run"}
      </Button>
      {!terminal ? (
        <Button
          size="sm"
          variant="danger"
          disabled={cancel.isPending}
          onClick={() => cancel.mutate({ reason: "cancelled from dashboard" })}
        >
          Cancel
        </Button>
      ) : null}
    </div>
  );
}
