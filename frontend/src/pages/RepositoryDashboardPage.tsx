import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  useCreateSnapshot,
  useGitContext,
  useRepository,
  useRepositoryHealth,
} from "../hooks/api/useRepositories";
import { useSettings } from "../hooks/useSettings";
import { forgetRepoId, rememberRepoId } from "../services/settingsStore";
import { EmptyState } from "../components/feedback/EmptyState";
import { LoadingBlock } from "../components/feedback/LoadingBlock";
import { QueryError } from "../components/feedback/QueryError";
import { Badge } from "../components/primitives/Badge";
import { Button } from "../components/primitives/Button";
import { Card, CardBody, CardHeader } from "../components/primitives/Card";
import { TextField } from "../components/primitives/Field";
import { Table, TD, TH, THead, TR } from "../components/primitives/Table";
import { SignalContributionsTable } from "../components/shared/SignalContributionsTable";
import { ClassificationBadge } from "../components/state/badges";
import { relativeTime } from "../lib/format";

export function RepositoryDashboardPage() {
  const { repoId } = useParams();
  return repoId ? <RepoDetail repoId={repoId} /> : <RepoRegistry />;
}

function RepoRegistry() {
  const { settings } = useSettings();
  const [track, setTrack] = useState("");
  const navigate = useNavigate();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Repositories</h1>
        <Link to="/tasks/new">
          <Button size="sm" variant="primary">
            Create task
          </Button>
        </Link>
      </div>

      <Card>
        <CardHeader
          title="Tracked repositories"
          subtitle="The backend has no list endpoint — this registry is stored in your browser."
        />
        <CardBody className="space-y-3">
          {settings.knownRepoIds.length === 0 ? (
            <EmptyState
              title="No repositories tracked yet"
              hint="Register one from Create Task, or paste a known repository id below."
            />
          ) : (
            <ul className="space-y-1">
              {settings.knownRepoIds.map((id) => (
                <li key={id} className="flex items-center justify-between gap-2 text-sm">
                  <Link to={`/repositories/${id}`} className="font-mono text-accent underline">
                    {id}
                  </Link>
                  <Button size="sm" variant="ghost" onClick={() => forgetRepoId(id)}>
                    Untrack
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <form
            className="flex items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const id = track.trim();
              if (id) {
                rememberRepoId(id);
                setTrack("");
                navigate(`/repositories/${id}`);
              }
            }}
          >
            <TextField
              label="Track a repository by id"
              value={track}
              onChange={(e) => setTrack(e.target.value)}
              placeholder="repo_…"
              className="font-mono"
            />
            <Button type="submit">Track</Button>
          </form>
        </CardBody>
      </Card>
    </div>
  );
}

function RepoDetail({ repoId }: { repoId: string }) {
  const repo = useRepository(repoId);
  const health = useRepositoryHealth(repoId);
  const git = useGitContext(repoId);
  const snapshot = useCreateSnapshot(repoId);

  if (repo.isLoading) return <LoadingBlock rows={5} />;
  if (repo.isError) return <QueryError error={repo.error} onRetry={() => repo.refetch()} />;
  if (!repo.data) return null;

  const r = repo.data;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold">{r.name}</h1>
          <p className="text-xs text-muted">
            {r.source_type} · <span className="font-mono">{r.url_or_path}</span> · id {r.id}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            disabled={snapshot.isPending}
            onClick={() => snapshot.mutate({ force: false })}
          >
            {snapshot.isPending ? "Creating snapshot…" : "Create snapshot"}
          </Button>
          <Link to={`/repositories/${r.id}/graph`}>
            <Button size="sm" variant="secondary">
              Knowledge graph
            </Button>
          </Link>
          <Link to="/tasks/new">
            <Button size="sm" variant="primary">
              New task
            </Button>
          </Link>
        </div>
      </div>

      {snapshot.data ? (
        <Card>
          <CardBody className="text-xs">
            Snapshot <span className="font-mono">{snapshot.data.snapshot_id}</span> ·{" "}
            <Badge tone="neutral">{snapshot.data.status}</Badge> · {snapshot.data.file_count} files
            {snapshot.data.limit_reason ? ` · ${snapshot.data.limit_reason}` : ""}
          </CardBody>
        </Card>
      ) : null}
      {snapshot.isError ? <QueryError error={snapshot.error} /> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Repository health" />
          <CardBody>
            {health.isLoading ? (
              <LoadingBlock rows={3} />
            ) : health.isError ? (
              <QueryError error={health.error} onRetry={() => health.refetch()} />
            ) : health.data ? (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <span className="text-3xl font-semibold tabular-nums">{health.data.value}</span>
                  <ClassificationBadge value={health.data.classification} />
                  <span className="text-xs text-muted">{health.data.model_version}</span>
                </div>
                <SignalContributionsTable signals={health.data.subscores} />
              </div>
            ) : null}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Risky modules" />
          <CardBody>
            {health.data?.risky_modules?.length ? (
              <Table>
                <THead>
                  <TR>
                    <TH>Path</TH>
                    <TH>Score</TH>
                    <TH>Centrality</TH>
                    <TH>Complexity</TH>
                  </TR>
                </THead>
                <tbody>
                  {health.data.risky_modules.map((m) => (
                    <TR key={m.path}>
                      <TD className="font-mono text-xs">{m.path}</TD>
                      <TD>{m.score.toFixed(2)}</TD>
                      <TD>{m.centrality.toFixed(2)}</TD>
                      <TD>{m.complexity.toFixed(2)}</TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            ) : (
              <p className="text-xs text-muted">No risky modules reported.</p>
            )}
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader title="Git activity" />
        <CardBody>
          {git.isLoading ? (
            <LoadingBlock rows={3} />
          ) : git.data && git.data.available ? (
            <div className="space-y-3 text-xs">
              <p className="text-muted">{git.data.commit_count} commits analysed</p>
              <ul className="space-y-1">
                {(git.data.commits ?? []).slice(0, 8).map((c) => (
                  <li key={c.sha} className="flex gap-2">
                    <span className="font-mono text-muted">{c.sha.slice(0, 7)}</span>
                    <span className="truncate">{c.message.split("\n")[0]}</span>
                    <span className="shrink-0 text-muted">{relativeTime(c.authored_at)}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-xs text-muted">
              {git.data?.reason ?? "No Git history available for this repository."}
            </p>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
