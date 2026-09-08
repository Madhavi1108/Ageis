import { Link } from "react-router-dom";

import {
  useChanges,
  useConfidence,
  useExecutions,
  useFailures,
  useImpact,
  useMapping,
  usePlan,
  useRegression,
  useRepairs,
  useReview,
  useRisk,
  useTests,
  useVerification,
} from "../../hooks/api/useTaskStages";
import { Badge } from "../../components/primitives/Badge";
import { ClassificationBadge, OutcomeBadge } from "../../components/state/badges";
import type { StageId } from "../../types/pipeline";
import { PanelShell } from "./PanelShell";

interface Props {
  taskId: string;
  open: boolean;
}

function OpenFull({ to, label }: { to: string; label: string }) {
  return (
    <Link to={to} className="text-xs text-accent underline">
      {label} →
    </Link>
  );
}

function IngestPanel() {
  return <p className="text-xs text-muted">Repository snapshot ingested. See the Repository Dashboard.</p>;
}

function AnalyzePanel({ taskId, open }: Props) {
  const mapping = useMapping(taskId, { enabled: open });
  const impact = useImpact(taskId, { enabled: open });
  return (
    <div className="space-y-2">
      <PanelShell query={mapping} notReady="Mapping not produced yet.">
        {(m) => (
          <p className="text-xs">
            {m.candidates.length} mapped location{m.candidates.length === 1 ? "" : "s"} · overall
            confidence {(m.overall_confidence * 100).toFixed(0)}%
          </p>
        )}
      </PanelShell>
      <PanelShell query={impact} notReady="Impact analysis not produced yet.">
        {(i) => (
          <p className="text-xs">
            {(i.changed_set.files ?? []).length} impacted file(s), {i.related_tests.length} related
            test(s), {i.public_api_touched.length} public API touched
          </p>
        )}
      </PanelShell>
      <OpenFull to={`/tasks/${taskId}/impact`} label="Open impact view" />
    </div>
  );
}

function PlanPanel({ taskId, open }: Props) {
  const plan = usePlan(taskId, { enabled: open });
  return (
    <div className="space-y-2">
      <PanelShell query={plan} notReady="Plan not generated yet.">
        {(p) => (
          <p className="flex flex-wrap items-center gap-2 text-xs">
            <Badge tone="neutral">v{p.version}</Badge>
            {p.steps.length} step(s)
            {p.validation ? <ClassificationBadge value={p.validation.verdict} /> : null}
          </p>
        )}
      </PanelShell>
      <OpenFull to={`/tasks/${taskId}/plan`} label="Open planning view" />
    </div>
  );
}

function ImplementPanel({ taskId, open }: Props) {
  const changes = useChanges(taskId, { enabled: open });
  return (
    <div className="space-y-2">
      <PanelShell query={changes} notReady="No implementation generated yet.">
        {(c) => (
          <p className="flex flex-wrap items-center gap-2 text-xs">
            <Badge tone="neutral">v{c.version}</Badge>
            {c.patch.touched_paths.length} file(s) · {c.patch.diff_size} bytes
            {c.scope_violations.length ? (
              <Badge tone="danger">{c.scope_violations.length} scope violation(s)</Badge>
            ) : (
              <Badge tone="success">in scope</Badge>
            )}
          </p>
        )}
      </PanelShell>
      <OpenFull to={`/tasks/${taskId}/changes`} label="Open diff view" />
    </div>
  );
}

function TestsPanel({ taskId, open }: Props) {
  const tests = useTests(taskId, { enabled: open });
  return (
    <div className="space-y-2">
      <PanelShell query={tests} notReady="No tests generated yet.">
        {(t) => (
          <p className="text-xs">
            {t.test_cases.length} generated test(s) · {t.targeted_set.length} targeted symbol(s)
          </p>
        )}
      </PanelShell>
      <OpenFull to={`/tasks/${taskId}/tests`} label="Open test view" />
    </div>
  );
}

function ExecutePanel({ taskId, open }: Props) {
  const execs = useExecutions(taskId, { enabled: open });
  return (
    <div className="space-y-2">
      <PanelShell query={execs} notReady="Tests not executed yet.">
        {(list) =>
          list.length ? (
            <p className="flex flex-wrap items-center gap-2 text-xs">
              latest <OutcomeBadge outcome={list[0].outcome} />
              {list[0].results.length} result(s) · {list.length} run(s)
            </p>
          ) : (
            <p className="text-xs text-muted">No executions recorded.</p>
          )
        }
      </PanelShell>
      <OpenFull to={`/tasks/${taskId}/tests`} label="Open test view" />
    </div>
  );
}

function InvestigatePanel({ taskId, open }: Props) {
  const failures = useFailures(taskId, { enabled: open });
  return (
    <div className="space-y-2">
      <PanelShell query={failures} notReady="No failure investigation (tests passed).">
        {(f) => (
          <p className="text-xs">
            {f.failures.length} failing test(s) · {f.facts.length} fact(s), {f.inferences.length}{" "}
            inference(s)
          </p>
        )}
      </PanelShell>
      <OpenFull to={`/tasks/${taskId}/debugging`} label="Open debugging timeline" />
    </div>
  );
}

function RepairPanel({ taskId, open }: Props) {
  const repairs = useRepairs(taskId, { enabled: open });
  return (
    <div className="space-y-2">
      <PanelShell query={repairs} notReady="Repair loop did not run.">
        {(r) => (
          <p className="flex flex-wrap items-center gap-2 text-xs">
            <OutcomeBadge outcome={r.outcome} />
            {r.attempts.length} attempt(s)
            {r.best_iteration != null ? ` · best #${r.best_iteration}` : ""}
          </p>
        )}
      </PanelShell>
      <OpenFull to={`/tasks/${taskId}/debugging`} label="Open debugging timeline" />
    </div>
  );
}

function RegressionPanel({ taskId, open }: Props) {
  const regression = useRegression(taskId, { enabled: open });
  return (
    <div className="space-y-2">
      <PanelShell query={regression} notReady="Regression selection not produced yet.">
        {(r) => (
          <p className="flex flex-wrap items-center gap-2 text-xs">
            {r.plan.tests.length}/{r.plan.full_suite_count} test(s) selected
            {r.executed ? <Badge tone="neutral">executed</Badge> : null}
            {r.new_failures && r.new_failures.length ? (
              <Badge tone="danger">{r.new_failures.length} new failure(s)</Badge>
            ) : null}
          </p>
        )}
      </PanelShell>
      <OpenFull to={`/tasks/${taskId}/debugging`} label="Open debugging timeline" />
    </div>
  );
}

function ReviewPanel({ taskId, open }: Props) {
  const review = useReview(taskId, { enabled: open });
  return (
    <div className="space-y-2">
      <PanelShell query={review} notReady="Review not produced yet.">
        {(r) => (
          <p className="flex flex-wrap items-center gap-2 text-xs">
            {r.findings.length} finding(s)
            {r.blocking ? <Badge tone="danger">blocking</Badge> : <Badge tone="success">non-blocking</Badge>}
          </p>
        )}
      </PanelShell>
      <OpenFull to={`/tasks/${taskId}/review`} label="Open review findings" />
    </div>
  );
}

function VerifyPanel({ taskId, open }: Props) {
  const verification = useVerification(taskId, { enabled: open });
  const risk = useRisk(taskId, { enabled: open });
  const confidence = useConfidence(taskId, { enabled: open });
  return (
    <div className="space-y-2">
      <PanelShell query={verification} notReady="Verification not produced yet.">
        {(v) => {
          const mandatory = v.criteria.filter((c) => c.mandatory);
          const pass = mandatory.filter((c) => c.verdict === "PASS").length;
          return (
            <p className="flex flex-wrap items-center gap-2 text-xs">
              <ClassificationBadge value={v.verdict} />
              {pass}/{mandatory.length} mandatory criteria passed
            </p>
          );
        }}
      </PanelShell>
      <div className="flex flex-wrap gap-2 text-xs">
        {risk.data ? (
          <span className="inline-flex items-center gap-1">
            risk <ClassificationBadge value={risk.data.classification} />
          </span>
        ) : null}
        {confidence.data ? (
          <span className="inline-flex items-center gap-1">
            confidence <ClassificationBadge value={confidence.data.classification} />
          </span>
        ) : null}
      </div>
      <OpenFull to={`/tasks/${taskId}/verification`} label="Open verification result" />
    </div>
  );
}

const REGISTRY: Record<StageId, (p: Props) => JSX.Element> = {
  ingest: () => <IngestPanel />,
  analyze: (p) => <AnalyzePanel {...p} />,
  plan: (p) => <PlanPanel {...p} />,
  validate: (p) => <PlanPanel {...p} />,
  implement: (p) => <ImplementPanel {...p} />,
  generate_tests: (p) => <TestsPanel {...p} />,
  execute: (p) => <ExecutePanel {...p} />,
  investigate: (p) => <InvestigatePanel {...p} />,
  repair: (p) => <RepairPanel {...p} />,
  execute_retry: (p) => <ExecutePanel {...p} />,
  regression: (p) => <RegressionPanel {...p} />,
  review: (p) => <ReviewPanel {...p} />,
  verify: (p) => <VerifyPanel {...p} />,
};

export function StagePanelContent({ stageId, taskId, open }: { stageId: StageId } & Props) {
  const Render = REGISTRY[stageId];
  return <Render taskId={taskId} open={open} />;
}
