import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { useReview } from "../hooks/api/useTaskStages";
import { EmptyState } from "../components/feedback/EmptyState";
import { LoadingBlock } from "../components/feedback/LoadingBlock";
import { ErrorEnvelopeAlert } from "../components/feedback/ErrorEnvelopeAlert";
import { isStageNotReady } from "../services/errorMessages";
import { Badge } from "../components/primitives/Badge";
import { Card, CardBody, CardHeader } from "../components/primitives/Card";
import { SelectField } from "../components/primitives/Field";
import { EvidenceList } from "../components/shared/EvidenceList";
import { SeverityBadge } from "../components/state/badges";

export function ReviewFindingsPage() {
  const { taskId = "" } = useParams();
  const review = useReview(taskId);
  const [severity, setSeverity] = useState("");
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");

  const filtered = useMemo(() => {
    const items = review.data?.findings ?? [];
    return items.filter(
      (f) =>
        (!severity || f.severity === severity) &&
        (!category || f.category === category) &&
        (!source || f.source === source),
    );
  }, [review.data, severity, category, source]);

  if (review.isLoading) return <LoadingBlock rows={5} />;
  if (review.isError && isStageNotReady(review.error))
    return <EmptyState title="No review produced yet." />;
  if (review.isError) return <ErrorEnvelopeAlert error={review.error} />;
  if (!review.data) return null;

  const r = review.data;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Code review"
          subtitle={`implementation v${r.implementation_version} · tools: ${r.static_tools_run.join(", ") || "—"}`}
          actions={
            r.blocking ? <Badge tone="danger">blocking</Badge> : <Badge tone="success">non-blocking</Badge>
          }
        />
        <CardBody className="flex flex-wrap gap-2 text-xs">
          {Object.entries(r.counts_by_severity).map(([k, v]) => (
            <Badge key={k} tone="neutral">
              {k}: {v}
            </Badge>
          ))}
        </CardBody>
      </Card>

      <Card>
        <CardBody className="grid gap-3 sm:grid-cols-3">
          <SelectField label="Severity" value={severity} onChange={(e) => setSeverity(e.target.value)}>
            <option value="">any</option>
            {["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </SelectField>
          <SelectField label="Category" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">any</option>
            {[...new Set(r.findings.map((f) => f.category))].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </SelectField>
          <SelectField label="Source" value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="">any</option>
            {["STATIC", "RULE", "AI"].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </SelectField>
        </CardBody>
      </Card>

      {filtered.length === 0 ? (
        <EmptyState title="No findings match the filters." />
      ) : (
        <div className="space-y-2">
          {filtered.map((f, i) => (
            <Card key={i}>
              <CardBody className="space-y-1 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <SeverityBadge severity={f.severity} />
                  <Badge tone="neutral">{f.category}</Badge>
                  <Badge tone="neutral">{f.source}</Badge>
                  <Badge tone="neutral">{f.status}</Badge>
                  <span className="font-mono text-xs">
                    {f.file ?? "—"}
                    {f.line_start ? `:${f.line_start}` : ""}
                    {f.line_end && f.line_end !== f.line_start ? `-${f.line_end}` : ""}
                  </span>
                </div>
                <p>{f.description}</p>
                {f.recommendation ? <p className="text-muted">Fix: {f.recommendation}</p> : null}
                <EvidenceList evidence={f.evidence} />
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
