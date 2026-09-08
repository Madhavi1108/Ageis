import { useParams } from "react-router-dom";

import { useExecutions, useTests } from "../hooks/api/useTaskStages";
import { useRerunTests } from "../hooks/api/useTaskMutations";
import { EmptyState } from "../components/feedback/EmptyState";
import { LoadingBlock } from "../components/feedback/LoadingBlock";
import { ErrorEnvelopeAlert } from "../components/feedback/ErrorEnvelopeAlert";
import { isStageNotReady } from "../services/errorMessages";
import { Badge } from "../components/primitives/Badge";
import { Button } from "../components/primitives/Button";
import { Card, CardBody, CardHeader } from "../components/primitives/Card";
import { Table, TD, TH, THead, TR } from "../components/primitives/Table";
import { OutcomeBadge } from "../components/state/badges";
import { absoluteTime, duration } from "../lib/format";

export function TestExecutionPage() {
  const { taskId = "" } = useParams();
  const tests = useTests(taskId);
  const execs = useExecutions(taskId);
  const rerun = useRerunTests(taskId);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Generated tests"
          actions={
            <Button size="sm" onClick={() => rerun.mutate()} disabled={rerun.isPending}>
              {rerun.isPending ? "Running…" : "Run tests"}
            </Button>
          }
        />
        <CardBody>
          {rerun.isError ? <ErrorEnvelopeAlert error={rerun.error} className="mb-2" /> : null}
          {tests.isLoading ? (
            <LoadingBlock rows={3} />
          ) : tests.isError && isStageNotReady(tests.error) ? (
            <EmptyState title="No tests generated yet." />
          ) : tests.isError ? (
            <ErrorEnvelopeAlert error={tests.error} />
          ) : tests.data ? (
            <Table>
              <THead>
                <TR>
                  <TH>Name</TH>
                  <TH>Target</TH>
                  <TH>Kind</TH>
                  <TH>Status</TH>
                </TR>
              </THead>
              <tbody>
                {tests.data.test_cases.map((tc) => (
                  <TR key={tc.path + tc.name}>
                    <TD>
                      <div>{tc.name}</div>
                      <div className="font-mono text-[11px] text-muted">{tc.path}</div>
                      <div className="text-[11px] text-muted">{tc.rationale}</div>
                    </TD>
                    <TD className="font-mono text-xs">{tc.target_symbol}</TD>
                    <TD>
                      <Badge tone="neutral">{tc.kind}</Badge>
                    </TD>
                    <TD>
                      <OutcomeBadge outcome={tc.status} />
                      {tc.invalid_reason ? (
                        <div className="text-[11px] text-failed">{tc.invalid_reason}</div>
                      ) : null}
                    </TD>
                  </TR>
                ))}
              </tbody>
            </Table>
          ) : null}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Executions" />
        <CardBody className="space-y-3">
          {execs.isLoading ? (
            <LoadingBlock rows={3} />
          ) : execs.isError && isStageNotReady(execs.error) ? (
            <EmptyState title="Tests not executed yet." />
          ) : execs.isError ? (
            <ErrorEnvelopeAlert error={execs.error} />
          ) : execs.data && execs.data.length ? (
            execs.data.map((ex) => (
              <div key={ex.id} className="rounded border border-border p-2 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <OutcomeBadge outcome={ex.outcome} />
                  <Badge tone="neutral">v{ex.version}</Badge>
                  <span className="font-mono">exit {ex.exit_code}</span>
                  <span>{duration(ex.duration_ms)}</span>
                  <span className="text-muted">{absoluteTime(ex.created_at)}</span>
                </div>
                <div className="mt-1 font-mono text-[11px] text-muted">{ex.command}</div>
                {ex.reason ? <p className="mt-1 text-muted">{ex.reason}</p> : null}
                {ex.results.length ? (
                  <ul className="mt-1 space-y-0.5">
                    {ex.results.map((r) => (
                      <li key={r.test_id} className="flex items-center gap-2">
                        <OutcomeBadge outcome={r.outcome} />
                        <span className="font-mono">{r.test_id}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ))
          ) : (
            <EmptyState title="No executions recorded." />
          )}
        </CardBody>
      </Card>
    </div>
  );
}
