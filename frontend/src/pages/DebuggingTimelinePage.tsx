import { useParams } from "react-router-dom";

import { useFailures, useRegression, useRepairs } from "../hooks/api/useTaskStages";
import { EmptyState } from "../components/feedback/EmptyState";
import { LoadingBlock } from "../components/feedback/LoadingBlock";
import { ErrorEnvelopeAlert } from "../components/feedback/ErrorEnvelopeAlert";
import { isStageNotReady } from "../services/errorMessages";
import { Badge } from "../components/primitives/Badge";
import { Card, CardBody, CardHeader } from "../components/primitives/Card";
import { OutcomeBadge } from "../components/state/badges";

export function DebuggingTimelinePage() {
  const { taskId = "" } = useParams();
  const failures = useFailures(taskId);
  const repairs = useRepairs(taskId);
  const regression = useRegression(taskId);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="Failure investigation" />
        <CardBody>
          {failures.isLoading ? (
            <LoadingBlock rows={3} />
          ) : failures.isError && isStageNotReady(failures.error) ? (
            <EmptyState title="No failure investigation" hint="The tests passed, or the debug branch never ran." />
          ) : failures.isError ? (
            <ErrorEnvelopeAlert error={failures.error} />
          ) : failures.data ? (
            <div className="space-y-3 text-sm">
              <p className="text-xs text-muted">execution {failures.data.execution_id}</p>
              {failures.data.failures.map((f, i) => (
                <div key={i} className="rounded border border-border p-2 text-xs">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="danger">{f.failure_type}</Badge>
                    <span className="font-mono">{f.test_name}</span>
                    {f.exception_type ? <Badge tone="neutral">{f.exception_type}</Badge> : null}
                  </div>
                  {f.message ? <p className="mt-1">{f.message}</p> : null}
                  {(f.frames ?? []).length ? (
                    <ul className="mt-1 space-y-0.5 text-muted">
                      {(f.frames ?? []).map((fr, j) => (
                        <li key={j} className="font-mono">
                          {fr.in_diff ? "▸ " : "  "}
                          {fr.file}:{fr.lineno} {fr.symbol_id ? `(${fr.symbol_id})` : ""}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ))}
              <TwoCol
                a={{ title: "Facts", items: failures.data.facts }}
                b={{ title: "Inferences (hedged)", items: failures.data.inferences }}
              />
            </div>
          ) : null}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Bounded repair loop" />
        <CardBody>
          {repairs.isLoading ? (
            <LoadingBlock rows={3} />
          ) : repairs.isError && isStageNotReady(repairs.error) ? (
            <EmptyState title="Repair loop did not run." />
          ) : repairs.isError ? (
            <ErrorEnvelopeAlert error={repairs.error} />
          ) : repairs.data ? (
            <div className="space-y-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <OutcomeBadge outcome={repairs.data.outcome} />
                <Badge tone="neutral">{repairs.data.attempts.length} attempt(s)</Badge>
                {repairs.data.best_iteration != null ? (
                  <Badge tone="neutral">best #{repairs.data.best_iteration}</Badge>
                ) : null}
              </div>
              {repairs.data.attempts.map((a) => (
                <div key={a.iteration} className="rounded border border-border p-2 text-xs">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="neutral">#{a.iteration}</Badge>
                    <OutcomeBadge outcome={a.outcome} />
                    <span>
                      failing {a.failing_before} → {a.failing_after}
                    </span>
                    {a.regression_failures ? (
                      <Badge tone="danger">{a.regression_failures} regression</Badge>
                    ) : null}
                  </div>
                  <p className="mt-1 text-muted">{a.hypothesis}</p>
                </div>
              ))}
              {repairs.data.safe_stop ? (
                <div className="rounded border border-awaiting/40 bg-awaiting/10 p-2 text-xs">
                  <p className="font-medium">SAFE_STOP: {repairs.data.safe_stop.reason}</p>
                  <p className="mt-1">{repairs.data.safe_stop.failure_summary}</p>
                  <p className="mt-1 text-muted">
                    Recommended: {repairs.data.safe_stop.recommended_human_action}
                  </p>
                </div>
              ) : null}
            </div>
          ) : null}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Regression selection" />
        <CardBody>
          {regression.isLoading ? (
            <LoadingBlock rows={3} />
          ) : regression.isError && isStageNotReady(regression.error) ? (
            <EmptyState title="No regression selection yet." />
          ) : regression.isError ? (
            <ErrorEnvelopeAlert error={regression.error} />
          ) : regression.data ? (
            <div className="space-y-2 text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="neutral">mode {regression.data.plan.mode}</Badge>
                <Badge tone="neutral">
                  {regression.data.plan.tests.length}/{regression.data.plan.full_suite_count} selected
                </Badge>
                {regression.data.executed ? <Badge tone="neutral">executed</Badge> : null}
                {regression.data.new_failures?.length ? (
                  <Badge tone="danger">{regression.data.new_failures.length} new failure(s)</Badge>
                ) : null}
              </div>
              {regression.data.plan.subset_justification ? (
                <p className="text-muted">{regression.data.plan.subset_justification}</p>
              ) : null}
              <ul className="space-y-0.5">
                {regression.data.plan.tests.slice(0, 40).map((t) => (
                  <li key={t.test_id} className="flex items-center gap-2">
                    <Badge tone="neutral">{t.classification}</Badge>
                    <span className="font-mono">{t.test_id}</span>
                    <span className="text-muted">{t.rationale}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </CardBody>
      </Card>
    </div>
  );
}

function TwoCol({
  a,
  b,
}: {
  a: { title: string; items: string[] };
  b: { title: string; items: string[] };
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {[a, b].map((col) => (
        <div key={col.title}>
          <div className="text-xs font-medium">{col.title}</div>
          <ul className="mt-1 list-disc pl-4 text-xs text-muted">
            {col.items.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
