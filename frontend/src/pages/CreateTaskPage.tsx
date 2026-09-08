import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useCreateRepository } from "../hooks/api/useRepositories";
import { useCreateTask, useRunTask } from "../hooks/api/useTasks";
import { useGithubIssue } from "../hooks/api/useGithub";
import { useSettings } from "../hooks/useSettings";
import { useToast } from "../components/feedback/Toast";
import { ErrorEnvelopeAlert } from "../components/feedback/ErrorEnvelopeAlert";
import { Button } from "../components/primitives/Button";
import { Card, CardBody, CardHeader } from "../components/primitives/Card";
import { SelectField, TextArea, TextField } from "../components/primitives/Field";
import type { TaskCreate } from "../types/api";

const TYPES = ["", "BUG", "FEATURE", "REFACTOR", "REQUIREMENT", "QUESTION"] as const;

export function CreateTaskPage() {
  const navigate = useNavigate();
  const { notify } = useToast();
  const { settings } = useSettings();

  const [repositoryId, setRepositoryId] = useState(settings.knownRepoIds[0] ?? "");
  const [mode, setMode] = useState<"text" | "issue">("text");
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [taskType, setTaskType] = useState<(typeof TYPES)[number]>("");
  const [priority, setPriority] = useState<"LOW" | "NORMAL" | "HIGH">("NORMAL");
  const [allowedPaths, setAllowedPaths] = useState("");
  const [issueTitle, setIssueTitle] = useState("");
  const [issueBody, setIssueBody] = useState("");
  const [issueRef, setIssueRef] = useState("");
  const [runNow, setRunNow] = useState(true);

  const create = useCreateTask();
  const [createdId, setCreatedId] = useState<string | null>(null);
  const run = useRunTask(createdId ?? "");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const paths = allowedPaths
      .split(/[\n,]/)
      .map((p) => p.trim())
      .filter(Boolean);
    const body: TaskCreate = {
      repository_id: repositoryId.trim(),
      title: title.trim() || null,
      task_type: taskType || null,
      priority,
      allowed_paths: paths.length ? paths : null,
      created_by: settings.actorName || null,
      text: mode === "text" ? text : null,
      issue:
        mode === "issue"
          ? { source: "GITHUB", external_ref: issueRef || null, title: issueTitle, body: issueBody }
          : null,
    };
    create.mutate(body, {
      onSuccess: async (res) => {
        setCreatedId(res.task.id);
        notify(`Task ${res.task.id} created`, "success");
        if (runNow) {
          try {
            await run.mutateAsync();
          } catch {
            /* surfaced below */
          }
        }
        navigate(`/tasks/${res.task.id}`);
      },
    });
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-lg font-semibold">Create task</h1>

      <GithubImport
        onPrefill={(t, b, ref) => {
          setMode("issue");
          setIssueTitle(t);
          setIssueBody(b);
          setIssueRef(ref);
        }}
      />

      <Card>
        <CardHeader title="Task" />
        <CardBody>
          <form className="space-y-3" onSubmit={submit}>
            <TextField
              label="Repository id"
              required
              value={repositoryId}
              onChange={(e) => setRepositoryId(e.target.value)}
              placeholder="repo_…"
              className="font-mono"
              hint={
                settings.knownRepoIds.length
                  ? `tracked: ${settings.knownRepoIds.join(", ")}`
                  : "register a repository below or paste an id"
              }
            />

            <div className="flex gap-3 text-sm">
              <label className="flex items-center gap-1.5">
                <input
                  type="radio"
                  checked={mode === "text"}
                  onChange={() => setMode("text")}
                />
                Free text
              </label>
              <label className="flex items-center gap-1.5">
                <input
                  type="radio"
                  checked={mode === "issue"}
                  onChange={() => setMode("issue")}
                />
                Structured issue
              </label>
            </div>

            {mode === "text" ? (
              <TextArea
                label="Issue / bug / feature text"
                required
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={5}
              />
            ) : (
              <div className="space-y-3">
                <TextField
                  label="Issue title"
                  required
                  value={issueTitle}
                  onChange={(e) => setIssueTitle(e.target.value)}
                />
                <TextArea
                  label="Issue body"
                  required
                  value={issueBody}
                  onChange={(e) => setIssueBody(e.target.value)}
                  rows={4}
                />
                <TextField
                  label="External ref (e.g. issue number)"
                  value={issueRef}
                  onChange={(e) => setIssueRef(e.target.value)}
                />
              </div>
            )}

            <div className="grid gap-3 sm:grid-cols-3">
              <TextField
                label="Title (optional)"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
              <SelectField
                label="Type"
                value={taskType}
                onChange={(e) => setTaskType(e.target.value as (typeof TYPES)[number])}
              >
                {TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t || "infer"}
                  </option>
                ))}
              </SelectField>
              <SelectField
                label="Priority"
                value={priority}
                onChange={(e) => setPriority(e.target.value as "LOW" | "NORMAL" | "HIGH")}
              >
                {["LOW", "NORMAL", "HIGH"].map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </SelectField>
            </div>

            <TextArea
              label="Allowed paths (scope allowlist — one glob per line)"
              value={allowedPaths}
              onChange={(e) => setAllowedPaths(e.target.value)}
              rows={2}
              placeholder={"src/**\ninvoice.py"}
            />

            <label className="flex items-center gap-1.5 text-sm">
              <input type="checkbox" checked={runNow} onChange={(e) => setRunNow(e.target.checked)} />
              Run the pipeline immediately after creating
            </label>

            {create.isError ? <ErrorEnvelopeAlert error={create.error} /> : null}
            {run.isError ? <ErrorEnvelopeAlert error={run.error} /> : null}

            <Button type="submit" variant="primary" disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create task"}
            </Button>
          </form>
        </CardBody>
      </Card>

      <RegisterRepo onRegistered={(id) => setRepositoryId(id)} />
    </div>
  );
}

function RegisterRepo({ onRegistered }: { onRegistered: (id: string) => void }) {
  const create = useCreateRepository();
  const [sourceType, setSourceType] = useState<"LOCAL" | "GITHUB">("LOCAL");
  const [urlOrPath, setUrlOrPath] = useState("");
  const [name, setName] = useState("");

  return (
    <Card>
      <CardHeader title="Register a repository" subtitle="Adds it to your tracked list" />
      <CardBody>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate(
              {
                source_type: sourceType,
                url_or_path: urlOrPath.trim(),
                name: name.trim() || null,
              },
              { onSuccess: (repo) => onRegistered(repo.id) },
            );
          }}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <SelectField
              label="Source"
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value as "LOCAL" | "GITHUB")}
            >
              <option value="LOCAL">LOCAL</option>
              <option value="GITHUB">GITHUB</option>
            </SelectField>
            <TextField label="Name (optional)" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <TextField
            label={sourceType === "LOCAL" ? "Local path" : "Repository URL"}
            required
            value={urlOrPath}
            onChange={(e) => setUrlOrPath(e.target.value)}
          />
          {create.isError ? <ErrorEnvelopeAlert error={create.error} /> : null}
          {create.data ? (
            <p className="text-xs text-done">
              Registered <span className="font-mono">{create.data.id}</span>
            </p>
          ) : null}
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Registering…" : "Register"}
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}

function GithubImport({
  onPrefill,
}: {
  onPrefill: (title: string, body: string, ref: string) => void;
}) {
  const [owner, setOwner] = useState("");
  const [repo, setRepo] = useState("");
  const [number, setNumber] = useState("");
  const [enabled, setEnabled] = useState(false);
  const issue = useGithubIssue(owner, repo, Number(number) || undefined, { enabled });

  return (
    <Card>
      <CardHeader title="Prefill from a GitHub issue" subtitle="Optional" />
      <CardBody>
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setEnabled(true);
          }}
        >
          <TextField label="Owner" value={owner} onChange={(e) => setOwner(e.target.value)} />
          <TextField label="Repo" value={repo} onChange={(e) => setRepo(e.target.value)} />
          <TextField
            label="Issue #"
            value={number}
            onChange={(e) => setNumber(e.target.value)}
            inputMode="numeric"
          />
          <Button type="submit" disabled={!owner || !repo || !number}>
            Fetch
          </Button>
        </form>
        {issue.isError ? <ErrorEnvelopeAlert error={issue.error} className="mt-2" /> : null}
        {issue.data ? (
          <div className="mt-2 space-y-2 text-sm">
            <p className="font-medium">{issue.data.title}</p>
            <p className="line-clamp-3 whitespace-pre-wrap text-xs text-muted">{issue.data.body}</p>
            <Button
              size="sm"
              onClick={() =>
                onPrefill(issue.data!.title, issue.data!.body, String(issue.data!.number))
              }
            >
              Use this issue
            </Button>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}
