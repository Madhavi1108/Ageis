import { Link, useParams } from "react-router-dom";

import { useImpact, useMapping } from "../hooks/api/useTaskStages";
import { useTask } from "../hooks/api/useTasks";
import { EmptyState } from "../components/feedback/EmptyState";
import { LoadingBlock } from "../components/feedback/LoadingBlock";
import { ErrorEnvelopeAlert } from "../components/feedback/ErrorEnvelopeAlert";
import { isStageNotReady } from "../services/errorMessages";
import { Badge } from "../components/primitives/Badge";
import { Card, CardBody, CardHeader } from "../components/primitives/Card";
import { Table, TD, TH, THead, TR } from "../components/primitives/Table";
import { EvidenceList } from "../components/shared/EvidenceList";

export function CodeImpactPage() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  const mapping = useMapping(taskId);
  const impact = useImpact(taskId);
  const repoId = task.data?.repository_id;
  const snapshotId = task.data?.snapshot_id;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="Issue → code mapping" />
        <CardBody>
          {mapping.isLoading ? (
            <LoadingBlock rows={3} />
          ) : mapping.isError && isStageNotReady(mapping.error) ? (
            <EmptyState title="No mapping produced yet." />
          ) : mapping.isError ? (
            <ErrorEnvelopeAlert error={mapping.error} />
          ) : mapping.data ? (
            <div className="space-y-2">
              <p className="text-xs text-muted">
                overall confidence {(mapping.data.overall_confidence * 100).toFixed(0)}% ·
                semantic retrieval {mapping.data.semantic_available ? "available" : "unavailable"}
              </p>
              <Table>
                <THead>
                  <TR>
                    <TH>Path</TH>
                    <TH>Symbols</TH>
                    <TH>Confidence</TH>
                    <TH>Score</TH>
                  </TR>
                </THead>
                <tbody>
                  {mapping.data.candidates.map((c) => (
                    <TR key={c.path}>
                      <TD className="font-mono text-xs">
                        {repoId && snapshotId ? (
                          <Link
                            className="text-accent underline"
                            to={`/repositories/${repoId}/graph?snapshot=${snapshotId}&node=${encodeURIComponent(
                              c.path,
                            )}`}
                          >
                            {c.path}
                          </Link>
                        ) : (
                          c.path
                        )}
                      </TD>
                      <TD className="font-mono text-xs">{(c.symbols ?? []).join(", ") || "—"}</TD>
                      <TD>{(c.confidence * 100).toFixed(0)}%</TD>
                      <TD>{c.score.toFixed(3)}</TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
              {mapping.data.candidates[0]?.evidence ? (
                <EvidenceList evidence={mapping.data.candidates[0].evidence} />
              ) : null}
            </div>
          ) : null}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Impact analysis" />
        <CardBody>
          {impact.isLoading ? (
            <LoadingBlock rows={3} />
          ) : impact.isError && isStageNotReady(impact.error) ? (
            <EmptyState title="No impact analysis produced yet." />
          ) : impact.isError ? (
            <ErrorEnvelopeAlert error={impact.error} />
          ) : impact.data ? (
            <div className="space-y-3 text-sm">
              <div className="flex flex-wrap gap-2">
                <Badge tone="neutral">
                  {(impact.data.changed_set.files ?? []).length} changed file(s)
                </Badge>
                <Badge tone="neutral">
                  {(impact.data.changed_set.symbols ?? []).length} changed symbol(s)
                </Badge>
                <Badge tone="neutral">{impact.data.related_tests.length} related test(s)</Badge>
                <Badge tone="neutral">
                  {impact.data.public_api_touched.length} public API touched
                </Badge>
              </div>

              <Section title="Changed files" items={impact.data.changed_set.files ?? []} />
              <Section title="Related tests" items={impact.data.related_tests} />

              {impact.data.regression_areas.length ? (
                <div>
                  <div className="text-xs font-medium">Regression areas</div>
                  <ul className="mt-1 space-y-0.5 text-xs text-muted">
                    {impact.data.regression_areas.map((a) => (
                      <li key={a.path}>
                        <span className="font-mono">{a.path}</span> — {a.reason} (
                        {a.score.toFixed(2)})
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <details className="text-xs">
                <summary className="cursor-pointer text-accent">Rendered report</summary>
                <pre className="mt-1 overflow-auto whitespace-pre-wrap rounded bg-surface-2 p-2">
                  {impact.data.report}
                </pre>
              </details>
            </div>
          ) : null}
        </CardBody>
      </Card>
    </div>
  );
}

function Section({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <div className="text-xs font-medium">{title}</div>
      <ul className="mt-1 list-disc pl-4 text-xs font-mono text-muted">
        {items.map((x, i) => (
          <li key={i}>{x}</li>
        ))}
      </ul>
    </div>
  );
}
