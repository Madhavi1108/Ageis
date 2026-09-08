import { useParams } from "react-router-dom";

import { useConfidence, useRisk, useVerification } from "../hooks/api/useTaskStages";
import { useTask } from "../hooks/api/useTasks";
import { DecisionControls } from "../features/verification/DecisionControls";
import { EmptyState } from "../components/feedback/EmptyState";
import { LoadingBlock } from "../components/feedback/LoadingBlock";
import { ErrorEnvelopeAlert } from "../components/feedback/ErrorEnvelopeAlert";
import { isStageNotReady } from "../services/errorMessages";
import { Badge } from "../components/primitives/Badge";
import { Card, CardBody, CardHeader } from "../components/primitives/Card";
import { Table, TD, TH, THead, TR } from "../components/primitives/Table";
import { EvidenceList } from "../components/shared/EvidenceList";
import { ScoreDial } from "../components/shared/ScoreDial";
import { ClassificationBadge } from "../components/state/badges";
import { pct } from "../lib/format";

export function VerificationResultPage() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  const verification = useVerification(taskId);
  const risk = useRisk(taskId);
  const confidence = useConfidence(taskId);

  const showDecision =
    task.data?.state === "AWAITING_APPROVAL" || !!verification.data?.decision;

  return (
    <div className="space-y-4">
      {showDecision ? <DecisionControls taskId={taskId} /> : null}

      {verification.isLoading ? (
        <LoadingBlock rows={5} />
      ) : verification.isError && isStageNotReady(verification.error) ? (
        <EmptyState title="No verification produced yet." />
      ) : verification.isError ? (
        <ErrorEnvelopeAlert error={verification.error} />
      ) : verification.data ? (
        <>
          <Card>
            <CardHeader
              title={
                <span className="flex items-center gap-2">
                  Verdict <ClassificationBadge value={verification.data.verdict} />
                </span>
              }
              subtitle={`implementation v${verification.data.implementation_version} · resulting state ${verification.data.resulting_state} · ${verification.data.model_version}`}
            />
            <CardBody className="grid gap-2 sm:grid-cols-3">
              {risk.data ? (
                <ScoreDial
                  label="Change risk"
                  value={risk.data.value}
                  classification={risk.data.classification}
                  confidence={risk.data.overall_confidence}
                />
              ) : null}
              {confidence.data ? (
                <ScoreDial
                  label="Patch confidence"
                  value={confidence.data.value}
                  classification={confidence.data.classification}
                  confidence={confidence.data.overall_confidence}
                />
              ) : null}
              <div className="rounded-md border border-border bg-surface-2 px-3 py-2 text-xs">
                <div className="text-muted">Replay fidelity</div>
                <div className="mt-1 text-2xl font-semibold tabular-nums">
                  {verification.data.replay_fidelity != null
                    ? pct(verification.data.replay_fidelity)
                    : "—"}
                </div>
                <div className="text-muted">
                  confidence {pct(verification.data.confidence.value)} ({verification.data.confidence.basis})
                </div>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Criteria" />
            <CardBody>
              <Table>
                <THead>
                  <TR>
                    <TH>Criterion</TH>
                    <TH>Verdict</TH>
                    <TH>Mandatory</TH>
                    <TH>Detail</TH>
                  </TR>
                </THead>
                <tbody>
                  {verification.data.criteria.map((c) => (
                    <TR key={c.name}>
                      <TD>{c.name}</TD>
                      <TD>
                        <ClassificationBadge value={c.verdict} />
                      </TD>
                      <TD>{c.mandatory ? <Badge tone="neutral">required</Badge> : "—"}</TD>
                      <TD className="text-xs text-muted">
                        {c.detail}
                        <EvidenceList evidence={c.evidence} />
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            </CardBody>
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader title="Plan alignment" />
              <CardBody className="space-y-1 text-xs">
                <p>
                  {verification.data.plan_alignment.steps_implemented}/
                  {verification.data.plan_alignment.steps_total} steps implemented
                </p>
                <Listing
                  label="Unimplemented steps"
                  items={verification.data.plan_alignment.unimplemented_steps ?? []}
                />
                <Listing
                  label="Unplanned files"
                  items={verification.data.plan_alignment.unplanned_files ?? []}
                />
                <Listing
                  label="Files touched"
                  items={verification.data.plan_alignment.files_touched ?? []}
                />
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="Explainability trace" />
              <CardBody className="space-y-2 text-xs">
                <TraceBlock label="Why these files" items={verification.data.trace.why_file ?? []} />
                <p>
                  <span className="font-medium">Why this change:</span>{" "}
                  {verification.data.trace.why_change || "—"}
                </p>
                <TraceBlock label="Why these tests" items={verification.data.trace.why_test ?? []} />
                <p>
                  <span className="font-medium">Why it's safe:</span>{" "}
                  {verification.data.trace.why_safe || "—"}
                </p>
              </CardBody>
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
}

function Listing({ label, items }: { label: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <div className="font-medium">{label}</div>
      <ul className="list-disc pl-4 font-mono text-muted">
        {items.map((x, i) => (
          <li key={i}>{x}</li>
        ))}
      </ul>
    </div>
  );
}

function TraceBlock({ label, items }: { label: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <div className="font-medium">{label}</div>
      <ul className="list-disc pl-4 text-muted">
        {items.map((x, i) => (
          <li key={i}>{x}</li>
        ))}
      </ul>
    </div>
  );
}
