# AEGIS User Guide

Audience: someone submitting engineering tasks to AEGIS and reading the results.
For running the service see [`OPERATOR_GUIDE.md`](OPERATOR_GUIDE.md); for hacking
on it see [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md).

Status: final — reconciled against the built system (Phases 0–28), 2026-09-09.

---

## 1. What AEGIS does

You give AEGIS a **Git repository** and a **development task** (a bug report or a
feature request, in plain text). It drives the task through a fixed pipeline —
ingest, analyse, map the issue to code, plan, implement, generate tests, execute
them in a sandbox, debug and repair on failure, run regression tests, review,
score risk and confidence, and verify — and produces a **verified,
evidence-backed diff**, optionally opening a pull request.

Every conclusion it reaches carries evidence. When it is not sure, it says so
(`UNKNOWN`, `LOW CONFIDENCE`) rather than guessing. It never claims a test
passed unless that test executed and passed.

## 2. Submitting a task via the API

The API is served at `http://localhost:8000` by default (`uvicorn app.main:app`).
Interactive docs are at `/docs`, the full reference is
[`API_REFERENCE.md`](API_REFERENCE.md).

```bash
# 1. register the repository (local path inside a configured root, or a GitHub URL)
curl -sX POST localhost:8000/repositories \
  -H 'content-type: application/json' \
  -d '{"source_type": "LOCAL", "url_or_path": "/srv/repos/my-service"}'
# -> {"id": "<repo_id>", ...}

# 2. snapshot + analyse it
curl -sX POST localhost:8000/repositories/<repo_id>/snapshots -d '{}'
# -> {"snapshot_id": "<snap_id>", ...}
curl -sX POST localhost:8000/repositories/<repo_id>/snapshots/<snap_id>/analysis -d '{}'

# 3. create the task
curl -sX POST localhost:8000/tasks \
  -H 'content-type: application/json' \
  -d '{"repository_id": "<repo_id>",
       "text": "calculate_total() returns a negative number when the discount exceeds the price",
       "allowed_paths": ["invoice.py", "test_invoice.py"]}'
# -> {"task": {"id": "<task_id>", "state": "PENDING"}, ...}

# 4. run it (enqueues a job; the worker picks it up)
curl -sX POST localhost:8000/tasks/<task_id>/run
```

`allowed_paths` is the **scope**: the files AEGIS is permitted to change. Leave it
out to let the planner propose the scope, but an explicit scope is strongly
recommended — a change that strays outside it is flagged as a scope violation.

## 3. Watching progress

```bash
curl -s localhost:8000/tasks/<task_id>            # current state
curl -s localhost:8000/tasks/<task_id>/timeline   # per-stage history, durations, evidence
```

Or use the **dashboard** (`http://localhost:5173` in dev): the task pipeline view
shows each stage as it runs, the diff/patch viewer shows the proposed change with
per-file risk / scope / related-tests / review findings, and the trust report
shows the engineering trace and the deterministic-replay fidelity disclosure.

## 4. Task states and what to do

| State | Meaning | Your action |
|---|---|---|
| `PENDING` / `QUEUED` | accepted, waiting for the worker | wait |
| `INGESTING` … `VERIFYING` | a pipeline stage is running | wait; watch the timeline |
| `AWAITING_APPROVAL` | verification produced a `PARTIAL` verdict — a human must decide | review the diff + trust report, then approve or reject (below) |
| `COMPLETED` | verified change produced (and PR opened if configured) | review the diff / PR and merge |
| `PARTIALLY_SUPPORTED` | a limit or a missing capability stopped the full run; partial artifacts were produced | read `terminal_reason`; fix the limiting condition and resubmit |
| `FAILED` | something went wrong (bad plan, unrecoverable error) | read `terminal_reason` / timeline; refine the task text or scope |
| `CANCELLED` | you cancelled it, or a safe-stop fired | — |

`SAFE_STOP` inside the repair loop is not a separate state — the task lands in
`PARTIALLY_SUPPORTED` or `AWAITING_APPROVAL` with the repair evidence attached,
because the bounded loop stopped making progress rather than thrash.

### Approving a parked task

```bash
curl -sX POST localhost:8000/tasks/<task_id>/verification/decision \
  -H 'content-type: application/json' \
  -d '{"decision": "APPROVE", "reason": "reviewed the diff; boundary test covers it", "actor": "you@example.com"}'
```

Use `"decision": "REJECT"` to send it back. The decision, its reason and actor
are recorded in the audit log and the trust report.

## 5. `PARTIALLY_SUPPORTED` — the common causes

- **Docker not available** — the sandbox cannot run; analysis and planning still
  complete. Install Docker and resubmit.
- **Repository too large** — over one of the §37 limits (size, file count, file
  size, history depth). Raise the limit (operator) or narrow the repo.
- **Analysis budget exceeded** — a very large repo blew the analysis wall-clock
  budget; the un-analysed files are listed. Raise `AEGIS_LIMIT_ANALYSIS_SECONDS`.
- **Cost / wall-clock budget exceeded** — the orchestrator parked the task rather
  than overrun. An operator can extend the budget.
- **AI provider unavailable** — the circuit breaker is open after repeated
  upstream failures; retry after it resets.

## 6. Where the PR appears

If the operator configured a GitHub token **and** `AEGIS_ORCHESTRATOR_OPEN_PR` is
on **and** the target branch is not protected without an approval flag, a real PR
is opened and its URL is on the task (`GET /tasks/<id>` → `pull_request`). In all
other cases a **local PR artifact** (branch name, commit, PR title + body) is
still produced and attached — nothing is lost, and no PR is ever *claimed* unless
GitHub returned a 201 and a stored URL.

## 7. Limits you may hit

Defaults (all `AEGIS_*` configurable — see [`OPERATOR_GUIDE.md`](OPERATOR_GUIDE.md)):
repo 500 MiB, 25 000 files, 2 MiB/file, 500 commits of history, 300 s analysis,
~120k AI-context tokens, 40 generated tests/task, 4 repair iterations / 1200 s,
sandbox 600 s / 2 GiB / 2 CPU. Exceeding one degrades to `PARTIALLY_SUPPORTED`
with a reason — never a crash, never a silent truncation.
