import { useParams } from "react-router-dom";

import { usePlan } from "../hooks/api/useTaskStages";
import { useRegeneratePlan, useValidatePlan } from "../hooks/api/useTaskMutations";
import { EmptyState } from "../components/feedback/EmptyState";
import { LoadingBlock } from "../components/feedback/LoadingBlock";
import { ErrorEnvelopeAlert } from "../components/feedback/ErrorEnvelopeAlert";
import { isStageNotReady } from "../services/errorMessages";
import { Badge } from "../components/primitives/Badge";
import { Button } from "../components/primitives/Button";
import { Card, CardBody, CardHeader } from "../components/primitives/Card";
import { EvidenceList } from "../components/shared/EvidenceList";
import { ClassificationBadge } from "../components/state/badges";

export function PlanningPage() {
  const { taskId = "" } = useParams();
  const plan = usePlan(taskId);
  const regenerate = useRegeneratePlan(taskId);
  const validate = useValidatePlan(taskId);

  if (plan.isLoading) return <LoadingBlock rows={5} />;
  if (plan.isError && isStageNotReady(plan.error)) {
    return (
      <EmptyState
        title="No plan yet"
        hint="The planning stage has not produced an EngineeringPlan for this task."
        action={
          <Button size="sm" onClick={() => regenerate.mutate()} disabled={regenerate.isPending}>
            Generate a plan
          </Button>
        }
      />
    );
  }
  if (plan.isError) return <ErrorEnvelopeAlert error={plan.error} />;
  if (!plan.data) return null;

  const p = plan.data;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">v{p.version}</Badge>
        <Badge tone="neutral">{p.source}</Badge>
        {p.validation ? <ClassificationBadge value={p.validation.verdict} /> : null}
        <div className="ml-auto flex gap-2">
          <Button size="sm" onClick={() => validate.mutate()} disabled={validate.isPending}>
            Validate
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => regenerate.mutate()}
            disabled={regenerate.isPending}
          >
            Regenerate
          </Button>
        </div>
      </div>

      {(regenerate.isError || validate.isError) && (
        <ErrorEnvelopeAlert error={regenerate.error ?? validate.error} />
      )}

      <Card>
        <CardHeader title="Problem interpretation" />
        <CardBody className="space-y-2 text-sm">
          <p>{p.problem_interpretation}</p>
          <p className="text-muted">Expected behaviour: {p.expected_behavior}</p>
          {p.assumptions.length ? (
            <div>
              <div className="text-xs font-medium">Assumptions</div>
              <ul className="list-disc pl-4 text-xs text-muted">
                {p.assumptions.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title={`Steps (${p.steps.length})`} />
        <CardBody className="space-y-2">
          {p.steps.map((s, i) => (
            <div key={s.id} className="rounded border border-border p-2 text-sm">
              <div className="flex items-center gap-2">
                <Badge tone="neutral">{i + 1}</Badge>
                <span className="font-mono text-xs text-muted">{s.id}</span>
              </div>
              <p className="mt-1">{s.description}</p>
              <p className="mt-1 text-xs text-muted">Test intent: {s.test_intent}</p>
            </div>
          ))}
        </CardBody>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader title="Files & symbols" />
          <CardBody className="space-y-2 text-xs">
            <Listing label="Inspect" items={p.files_to_inspect} />
            <Listing label="Modify" items={p.files_to_modify} />
            <Listing label="Symbols" items={p.symbols_to_modify} />
            <Listing label="Dependencies" items={p.dependencies} />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Risk & rollback" />
          <CardBody className="space-y-2 text-xs">
            <Listing label="Regression risks" items={p.regression_risks} />
            <p>
              <span className="font-medium">Rollback:</span> {p.rollback_strategy}
            </p>
          </CardBody>
        </Card>
      </div>

      {p.validation ? (
        <Card>
          <CardHeader title="Plan validation" />
          <CardBody className="space-y-1 text-xs">
            <ClassificationBadge value={p.validation.verdict} />
            {(p.validation.reasons ?? []).map((r, i) => (
              <p key={i} className="text-muted">
                • {r}
              </p>
            ))}
          </CardBody>
        </Card>
      ) : null}

      <Card>
        <CardHeader title="Evidence" />
        <CardBody>
          <EvidenceList evidence={p.evidence} />
        </CardBody>
      </Card>
    </div>
  );
}

function Listing({ label, items }: { label: string; items: string[] }) {
  if (!items?.length) return null;
  return (
    <div>
      <div className="font-medium">{label}</div>
      <ul className="list-disc pl-4 text-muted">
        {items.map((x, i) => (
          <li key={i} className="font-mono">
            {x}
          </li>
        ))}
      </ul>
    </div>
  );
}
