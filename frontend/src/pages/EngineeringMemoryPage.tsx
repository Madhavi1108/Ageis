import { useState } from "react";
import { Link } from "react-router-dom";

import { useMemoryList, useMemorySearch } from "../hooks/api/useMemory";
import { EmptyState } from "../components/feedback/EmptyState";
import { LoadingBlock } from "../components/feedback/LoadingBlock";
import { ErrorEnvelopeAlert } from "../components/feedback/ErrorEnvelopeAlert";
import { Badge } from "../components/primitives/Badge";
import { Button } from "../components/primitives/Button";
import { Card, CardBody, CardHeader } from "../components/primitives/Card";
import { TextField } from "../components/primitives/Field";
import { relativeTime } from "../lib/format";

export function EngineeringMemoryPage() {
  const [repo, setRepo] = useState("");
  const [query, setQuery] = useState("");
  const list = useMemoryList(repo || undefined);
  const search = useMemorySearch();

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">Engineering memory</h1>

      <Card>
        <CardHeader title="Search prior tasks" subtitle="Lexical + symbol overlap + recency. Results are historical evidence, never authoritative." />
        <CardBody>
          <form
            className="flex flex-wrap items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (query.trim())
                search.mutate({ query: query.trim(), repository_id: repo || null, top_k: 10 });
            }}
          >
            <TextField
              label="Query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="min-w-[16rem]"
            />
            <TextField
              label="Repository id (optional)"
              value={repo}
              onChange={(e) => setRepo(e.target.value)}
              className="font-mono"
            />
            <Button type="submit" disabled={search.isPending || !query.trim()}>
              {search.isPending ? "Searching…" : "Search"}
            </Button>
          </form>

          {search.isError ? <ErrorEnvelopeAlert error={search.error} className="mt-2" /> : null}
          {search.data ? (
            <ul className="mt-3 space-y-2">
              {search.data.length === 0 ? (
                <EmptyState title="No matching prior tasks." />
              ) : (
                search.data.map((h) => (
                  <li key={h.task_id} className="rounded border border-border p-2 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone="accent">{(h.similarity * 100).toFixed(0)}% match</Badge>
                      <Badge tone="neutral">{h.label}</Badge>
                      {h.same_repository ? <Badge tone="neutral">same repo</Badge> : null}
                      {h.verification_verdict ? (
                        <Badge tone="neutral">{h.verification_verdict}</Badge>
                      ) : null}
                      <Link to={`/tasks/${h.task_id}`} className="text-xs text-accent underline">
                        {h.task_id}
                      </Link>
                    </div>
                    <p className="mt-1">{h.issue_summary}</p>
                    <p className="mt-1 text-xs text-muted">Fix: {h.fix_summary}</p>
                    <p className="mt-1 text-[11px] text-muted">{h.provenance}</p>
                  </li>
                ))
              )}
            </ul>
          ) : null}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Recent records" />
        <CardBody>
          {list.isLoading ? (
            <LoadingBlock rows={4} />
          ) : list.isError ? (
            <ErrorEnvelopeAlert error={list.error} />
          ) : list.data && list.data.length ? (
            <ul className="space-y-2">
              {list.data.map((m) => (
                <li key={m.id} className="rounded border border-border p-2 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="neutral">{m.outcome}</Badge>
                    {m.verification_verdict ? (
                      <Badge tone="neutral">{m.verification_verdict}</Badge>
                    ) : null}
                    <Link to={`/tasks/${m.task_id}`} className="text-xs text-accent underline">
                      {m.task_id}
                    </Link>
                    <span className="text-xs text-muted">{relativeTime(m.created_at)}</span>
                  </div>
                  <p className="mt-1">{m.issue_text_sanitized}</p>
                  <p className="mt-1 text-xs text-muted">Fix: {m.fix_summary}</p>
                  {(m.touched_files ?? []).length ? (
                    <p className="mt-1 font-mono text-[11px] text-muted">
                      {(m.touched_files ?? []).join(", ")}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title="No memory records"
              hint="Records are written when a task reaches COMPLETED / VERIFIED and memory is enabled on the backend."
            />
          )}
        </CardBody>
      </Card>
    </div>
  );
}
