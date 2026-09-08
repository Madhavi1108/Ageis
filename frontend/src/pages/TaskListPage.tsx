import { useState } from "react";
import { Link } from "react-router-dom";

import { useTaskList } from "../hooks/api/useTasks";
import { EmptyState } from "../components/feedback/EmptyState";
import { LoadingBlock } from "../components/feedback/LoadingBlock";
import { QueryError } from "../components/feedback/QueryError";
import { Button } from "../components/primitives/Button";
import { Card, CardBody } from "../components/primitives/Card";
import { SelectField, TextField } from "../components/primitives/Field";
import { Table, TD, TH, THead, TR } from "../components/primitives/Table";
import { TaskStateBadge } from "../components/state/badges";
import { relativeTime } from "../lib/format";
import { TASK_STATES } from "../types/pipeline";

const PAGE = 25;

export function TaskListPage() {
  const [repoId, setRepoId] = useState("");
  const [state, setState] = useState("");
  const [taskType, setTaskType] = useState("");
  const [offset, setOffset] = useState(0);

  const query = useTaskList({
    repository_id: repoId || undefined,
    state: state || undefined,
    task_type: taskType || undefined,
    limit: PAGE,
    offset,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Tasks</h1>
        <Link to="/tasks/new">
          <Button variant="primary" size="sm">
            New task
          </Button>
        </Link>
      </div>

      <Card>
        <CardBody className="grid gap-3 sm:grid-cols-3">
          <TextField
            label="Repository id"
            value={repoId}
            onChange={(e) => {
              setOffset(0);
              setRepoId(e.target.value);
            }}
            placeholder="filter by repo"
          />
          <SelectField
            label="State"
            value={state}
            onChange={(e) => {
              setOffset(0);
              setState(e.target.value);
            }}
          >
            <option value="">any</option>
            {TASK_STATES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Type"
            value={taskType}
            onChange={(e) => {
              setOffset(0);
              setTaskType(e.target.value);
            }}
          >
            <option value="">any</option>
            {["BUG", "FEATURE", "REFACTOR", "REQUIREMENT", "QUESTION"].map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </SelectField>
        </CardBody>
      </Card>

      {query.isLoading ? (
        <LoadingBlock rows={6} />
      ) : query.isError ? (
        <QueryError error={query.error} onRetry={() => query.refetch()} />
      ) : !query.data || query.data.items.length === 0 ? (
        <EmptyState
          title="No tasks"
          hint="Create a task to run it through the AEGIS pipeline."
          action={
            <Link to="/tasks/new" className="text-sm text-accent underline">
              Create a task
            </Link>
          }
        />
      ) : (
        <Card>
          <Table>
            <THead>
              <TR>
                <TH>Title</TH>
                <TH>Type</TH>
                <TH>State</TH>
                <TH>Updated</TH>
              </TR>
            </THead>
            <tbody>
              {query.data.items.map((t) => (
                <TR key={t.id}>
                  <TD>
                    <Link to={`/tasks/${t.id}`} className="text-accent underline">
                      {t.title}
                    </Link>
                    <div className="text-[11px] text-muted">{t.id}</div>
                  </TD>
                  <TD>{t.task_type}</TD>
                  <TD>
                    <TaskStateBadge state={t.state} />
                  </TD>
                  <TD className="whitespace-nowrap text-xs text-muted">
                    {relativeTime(t.updated_at)}
                  </TD>
                </TR>
              ))}
            </tbody>
          </Table>
          <CardBody className="flex items-center justify-between text-xs text-muted">
            <span>
              {offset + 1}–{offset + query.data.items.length} of {query.data.total}
            </span>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="ghost"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE))}
              >
                Prev
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={offset + PAGE >= query.data.total}
                onClick={() => setOffset(offset + PAGE)}
              >
                Next
              </Button>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
