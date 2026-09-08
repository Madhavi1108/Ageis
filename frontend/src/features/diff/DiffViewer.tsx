import { useMemo, useState } from "react";
import { Diff, Hunk, type FileData, type ViewType } from "react-diff-view";
import "react-diff-view/style/index.css";

import { EvidenceList } from "../../components/shared/EvidenceList";
import { SignalContributionsTable } from "../../components/shared/SignalContributionsTable";
import { Badge } from "../../components/primitives/Badge";
import { Button } from "../../components/primitives/Button";
import { Card, CardBody, CardHeader } from "../../components/primitives/Card";
import { CopyButton } from "../../components/primitives/CopyButton";
import { ClassificationBadge, SeverityBadge } from "../../components/state/badges";
import { absoluteTime } from "../../lib/format";
import type {
  ImplementationResult,
  PatchConfidence,
  PatchRiskAssessment,
  ReviewReport,
  TestGeneration,
} from "../../types/api";
import { changedLineCount, computeDiffStats } from "./diffStats";

const BIG_FILE_LINES = 800;

export interface DiffViewerProps {
  implementation: ImplementationResult;
  review?: ReviewReport;
  risk?: PatchRiskAssessment;
  confidence?: PatchConfidence;
  tests?: TestGeneration;
  decisionSlot?: React.ReactNode;
}

export function DiffViewer({
  implementation,
  review,
  risk,
  confidence,
  tests,
  decisionSlot,
}: DiffViewerProps) {
  const [viewType, setViewType] = useState<ViewType>("split");
  const stats = useMemo(
    () => computeDiffStats(implementation.patch.diff_text),
    [implementation.patch.diff_text],
  );
  const hasScopeViolation = implementation.scope_violations.length > 0;

  const findingFiles = new Set(
    (review?.findings ?? []).map((f) => f.file).filter((x): x is string => !!x),
  );

  return (
    <div className="space-y-3">
      <Card>
        <CardHeader
          title={
            <span className="flex flex-wrap items-center gap-2">
              Patch
              <Badge tone="neutral">v{implementation.version}</Badge>
              <Badge tone="neutral">{implementation.source}</Badge>
            </span>
          }
          subtitle={`snapshot ${implementation.snapshot_id} · ${absoluteTime(implementation.created_at)}`}
          actions={
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant={viewType === "split" ? "primary" : "secondary"}
                onClick={() => setViewType("split")}
              >
                Split
              </Button>
              <Button
                size="sm"
                variant={viewType === "unified" ? "primary" : "secondary"}
                onClick={() => setViewType("unified")}
              >
                Unified
              </Button>
            </div>
          }
        />
        <CardBody className="space-y-3">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span>
              <strong>{stats.fileStats.length}</strong> file
              {stats.fileStats.length === 1 ? "" : "s"} changed
            </span>
            <span className="text-done">+{stats.totalAdditions}</span>
            <span className="text-failed">−{stats.totalDeletions}</span>
            {hasScopeViolation ? (
              <Badge tone="danger">scope violations: {implementation.scope_violations.join(", ")}</Badge>
            ) : (
              <Badge tone="success">in scope</Badge>
            )}
            {review ? (
              <Badge tone={review.blocking ? "danger" : "neutral"}>
                {review.findings.length} review finding{review.findings.length === 1 ? "" : "s"}
                {review.blocking ? " · blocking" : ""}
              </Badge>
            ) : null}
          </div>

          {(risk || confidence) && (
            <div className="flex flex-wrap gap-2 text-xs">
              {risk ? (
                <span className="inline-flex items-center gap-1">
                  Risk <ClassificationBadge value={risk.classification} /> ({risk.value})
                </span>
              ) : null}
              {confidence ? (
                <span className="inline-flex items-center gap-1">
                  Confidence <ClassificationBadge value={confidence.classification} /> ({confidence.value})
                </span>
              ) : null}
            </div>
          )}

          {decisionSlot}
        </CardBody>
      </Card>

      <div className="grid gap-3 md:grid-cols-[220px_1fr]">
        <Card className="h-fit">
          <CardHeader title="Files" />
          <CardBody className="space-y-1">
            {stats.fileStats.map((fs) => (
              <a
                key={fs.key}
                href={`#file-${fs.key}`}
                className="flex items-center justify-between gap-2 rounded px-1.5 py-1 text-xs hover:bg-surface-2"
              >
                <span className="truncate font-mono" title={fs.path}>
                  {fs.path}
                </span>
                <span className="flex shrink-0 items-center gap-1">
                  {findingFiles.has(fs.path) ? <span className="text-awaiting">◆</span> : null}
                  <span className="text-done">+{fs.additions}</span>
                  <span className="text-failed">−{fs.deletions}</span>
                </span>
              </a>
            ))}
          </CardBody>
        </Card>

        <div className="min-w-0 space-y-3">
          {stats.files.map((file, idx) => (
            <DiffFile
              key={stats.fileStats[idx].key}
              anchorId={`file-${stats.fileStats[idx].key}`}
              file={file}
              viewType={viewType}
              flagged={findingFiles.has(stats.fileStats[idx].path)}
            />
          ))}

          <Card>
            <CardHeader
              title="Raw patch"
              actions={<CopyButton text={implementation.patch.diff_text} label="Copy patch" />}
            />
            <CardBody>
              <pre className="max-h-96 overflow-auto rounded bg-surface-2 p-2 text-xs">
                {implementation.patch.diff_text}
              </pre>
            </CardBody>
          </Card>

          <EditOpList implementation={implementation} tests={tests} />

          {review && review.findings.length > 0 ? (
            <Card>
              <CardHeader title="Review findings on this patch" />
              <CardBody className="space-y-2">
                {review.findings.map((f, i) => (
                  <div key={i} className="rounded border border-border p-2 text-xs">
                    <div className="flex flex-wrap items-center gap-2">
                      <SeverityBadge severity={f.severity} />
                      <Badge tone="neutral">{f.category}</Badge>
                      <Badge tone="neutral">{f.source}</Badge>
                      <span className="font-mono">
                        {f.file ?? "—"}
                        {f.line_start ? `:${f.line_start}` : ""}
                      </span>
                    </div>
                    <p className="mt-1">{f.description}</p>
                    {f.recommendation ? (
                      <p className="mt-1 text-muted">Fix: {f.recommendation}</p>
                    ) : null}
                  </div>
                ))}
              </CardBody>
            </Card>
          ) : null}

          {risk ? (
            <Card>
              <CardHeader title="Risk signal breakdown" />
              <CardBody>
                <SignalContributionsTable signals={risk.per_signal_contributions} />
              </CardBody>
            </Card>
          ) : null}
          {confidence ? (
            <Card>
              <CardHeader
                title="Confidence signal breakdown"
                subtitle={
                  confidence.hard_gate && confidence.hard_gate.length
                    ? `hard gate: ${confidence.hard_gate.join(", ")}`
                    : undefined
                }
              />
              <CardBody>
                <SignalContributionsTable signals={confidence.per_signal_contributions} />
              </CardBody>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function DiffFile({
  file,
  viewType,
  anchorId,
  flagged,
}: {
  file: FileData;
  viewType: ViewType;
  anchorId: string;
  flagged: boolean;
}) {
  const big = changedLineCount(file) > BIG_FILE_LINES;
  const [expanded, setExpanded] = useState(!big);
  const path = file.type === "delete" ? file.oldPath : file.newPath;

  return (
    <Card>
      <div id={anchorId} className="scroll-mt-4" />
      <CardHeader
        title={
          <span className="flex items-center gap-2 font-mono text-xs">
            {path}
            <Badge tone="neutral">{file.type}</Badge>
            {flagged ? <Badge tone="warn">has findings</Badge> : null}
          </span>
        }
        actions={
          big ? (
            <Button size="sm" variant="ghost" onClick={() => setExpanded((v) => !v)}>
              {expanded ? "Collapse" : `Expand (${changedLineCount(file)} lines)`}
            </Button>
          ) : undefined
        }
      />
      {expanded ? (
        <CardBody className="overflow-x-auto p-0">
          <Diff viewType={viewType} diffType={file.type} hunks={file.hunks}>
            {(hunks) => hunks.map((hunk) => <Hunk key={hunk.content} hunk={hunk} />)}
          </Diff>
        </CardBody>
      ) : null}
    </Card>
  );
}

function EditOpList({
  implementation,
  tests,
}: {
  implementation: ImplementationResult;
  tests?: TestGeneration;
}) {
  const traceability = implementation.traceability ?? {};
  const relatedTests = (tests?.test_cases ?? []).filter((tc) =>
    implementation.patch.touched_paths.some((p) => tc.target_symbol.includes(p) || p.includes(tc.path)),
  );

  return (
    <Card>
      <CardHeader
        title="Edit operations"
        subtitle="grouped by the plan step that produced them"
      />
      <CardBody className="space-y-3">
        {Object.keys(traceability).length > 0 ? (
          Object.entries(traceability).map(([stepId, paths]) => (
            <div key={stepId} className="rounded border border-border p-2">
              <div className="text-xs font-medium">
                plan step <span className="font-mono">{stepId}</span> →{" "}
                <span className="font-mono">{paths.join(", ")}</span>
              </div>
              <ul className="mt-1 space-y-2">
                {implementation.edit_ops
                  .filter((op) => op.plan_step_id === stepId)
                  .map((op, i) => (
                    <EditOpRow key={i} op={op} />
                  ))}
              </ul>
            </div>
          ))
        ) : (
          <ul className="space-y-2">
            {implementation.edit_ops.map((op, i) => (
              <EditOpRow key={i} op={op} />
            ))}
          </ul>
        )}

        {relatedTests.length > 0 ? (
          <div className="text-xs">
            <div className="font-medium">Related generated tests</div>
            <ul className="mt-1 list-disc pl-4 text-muted">
              {relatedTests.map((tc) => (
                <li key={tc.path}>
                  <span className="font-mono">{tc.path}</span> — {tc.name} ({tc.kind})
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}

function EditOpRow({ op }: { op: ImplementationResult["edit_ops"][number] }) {
  return (
    <li className="text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="accent">{op.op}</Badge>
        <span className="font-mono">{op.path}</span>
      </div>
      {op.anchor ? (
        <pre className="mt-1 overflow-x-auto rounded bg-surface-2 p-1.5 font-mono">{op.anchor}</pre>
      ) : null}
      <p className="mt-1 text-muted">{op.rationale}</p>
      <EvidenceList evidence={op.evidence} />
    </li>
  );
}
