# AEGIS Execution Model

Traceability: Specification §18, §19, §36, §37. Phase 0 deliverable (Spec §46 items 4, 5, 6, 15,
24, 25). Companion to `AEGIS_IMPLEMENTATION_PLAN.md` §4.3, §4.8–§4.9, §4.13; `ADR-0002`,
`ADR-0003`, `ADR-0010`, `ADR-0012`, `ADR-0013`.

Status: Accepted — 2026-09-04. Finalized in Phase 27 (retry/backoff/heartbeat, backpressure,
AI-context windowing, GC/retention, circuit breakers, `/readyz` + `/metrics`); reconciled
2026-09-09 (Phase 28) — no changes.

---

## 1. Layers of execution

| Layer | Runs where | Blocking? | Recorded |
|---|---|---|---|
| HTTP request | API process | must return fast | request id, route, status |
| Analysis job | Worker process | long-running, async | `Job` row: state, progress, attempts, checkpoint |
| Agent step | inside a job step | synchronous | `TaskStep`: agent, input_ref, output_ref, duration |
| Sandbox execution | short-lived `docker` container | synchronous within the step, wall-clock capped | `TestExecution`: command, outcome, resources, stdio artifacts |
| AI request | `AIProvider` | synchronous within the step, timed out | redacted metadata: provider, model, tokens, latency |

An HTTP request never blocks on an agent, the sandbox, or an AI call.

---

## 2. Job model (Spec §19)

`Job` fields: `id`, `task_id`, `type` (`INGEST`/`RUN_TASK`/`BENCHMARK`/`GC`), `state`
(`PENDING`/`QUEUED`/`RUNNING`/`SUCCEEDED`/`FAILED`/`CANCELLED`), `progress` (0..1), `attempts`,
`max_attempts`, `idempotency_key`, `dedupe_key`, `last_checkpoint` (`{phase, cursor}`),
`worker_id`, timestamps, `error`, `logs_artifact_id`.

- **IDs:** application-generated, sortable UUIDv7.
- **Idempotency:** `idempotency_key = hash(task_id, run_params)`; a duplicate submit returns the
  existing job.
- **Duplicate detection:** `dedupe_key = hash(repository_id, normalized_issue_text)`; a second
  job with the same `dedupe_key` while one is `PENDING/QUEUED/RUNNING` is rejected with a pointer
  to the in-flight job.
- **Retries (Phase 27):** a failed job is re-queued with a *real* not-before time —
  `Job.run_after = now + job_backoff_base_s * 2**(attempts-1)` — and `claim_next` skips a job
  whose `run_after` is still in the future, so the backoff is enforced, not merely logged.
  Retries stop at `max_attempts` (`job_max_attempts`, default 2). Deterministic failures are not
  retried at all: an `error.code` in `job_queue._TERMINAL_ERROR_CODES` (`PLAN_GENERATION_FAILED`,
  `IMPLEMENTATION_FAILED`, `TEST_GENERATION_FAILED`, `GENERATED_CODE_UNSAFE`,
  `TASK_INVALID_STATE`, `VALIDATION_ERROR`) goes straight to `FAILED`.
- **Cancellation:** cooperative — a `cancel` sets a flag the Orchestrator checks between phases and
  inside the repair loop; the current sandbox container is killed and removed.
- **Crash recovery (Phase 27):** the Worker checkpoints `last_checkpoint` and refreshes
  `Job.heartbeat_at` after every phase. `reclaim_orphans` re-queues a `RUNNING` job only when the
  newer of `heartbeat_at` / `started_at` is older than `worker_stale_after_s` — a job that
  heartbeats each stage is never reclaimed however long it legitimately runs. Phases are
  idempotent: re-running one overwrites its single output row.
- **Backpressure (Phase 27):** `enqueue_run` counts active jobs (`QUEUED` + `PENDING`) and rejects
  a new submission with `JOB_QUEUE_FULL` (HTTP 429, `{queue_depth, limit}`) once it reaches
  `job_max_queue_depth` (default 100). Idempotent re-submits of an already-queued job are exempt.
- **Concurrency / Worker:** the MVP worker is a **single sequential asyncio process** — one job at
  a time, one SQLite writer, a plain `SELECT ... LIMIT 1` + status claim (`ADR-0003`).
  `worker_max_concurrency` is a queue-admission denominator, **not** parallel execution; a
  distributed / parallel worker (and a per-repository cap) is a documented follow-up. The
  `orchestration/` abstraction keeps a queue library (arq/RQ) a drop-in.

---

## 3. Orchestrator loop

```
claim job -> load Task -> for phase in PIPELINE:
    check cancel flag
    check budgets (calls, cost, wall-clock)      # -> AWAITING_APPROVAL / PARTIALLY_SUPPORTED
    transition state (guarded)                    # illegal transition -> raise
    run the phase's agent/engine with typed input = previous phase's persisted output
    persist typed output + TaskStep + AuditLog
    checkpoint(job, phase)
-> terminal transition (COMPLETED / FAILED / CANCELLED / PARTIALLY_SUPPORTED)
-> write EngineeringMemory (on VERIFIED or SAFE_STOP)
-> emit final timeline event
```

The pipeline order and state machine are in `AEGIS_ARCHITECTURE.md` §6.

**Connectedness invariant:** each phase's input record must equal the prior phase's output record;
a Phase 21 test asserts this for a completed task.

---

## 4. Sandbox execution flow (Spec §18)

```
1. prepare        copy the RW workspace into an ephemeral dir (per execution)
2. build spec     from sandbox/policy.py: image@digest, --network none, --read-only,
                  --cap-drop ALL, --security-opt no-new-privileges, --pids-limit,
                  --cpus, --memory, --memory-swap, --ulimit nofile/nproc, non-root UID,
                  tmpfs /tmp, bind workspace :rw
3. scrub env      pass only the allowlisted vars (LANG, PATH, PYTHONHASHSEED=0, ...); no secrets
4. (optional) deps  network-restricted, host-allowlisted, hash-pinned install pre-step
5. run           the resolved test command (from RepositoryAnalysis, overridable),
                  wall-clock timeout -> SIGKILL
6. collect       exit code, JUnit-XML / JSON report, stdout/stderr (-> Artifacts),
                  resource usage (cpu_s, max_rss, wall_ms)
7. parse         -> per-test results; outcome in {PASS, FAIL, ERROR, TIMEOUT, OOM, INFRA_ERROR}
8. cleanup       always (finally): kill + remove container, remove volume, remove ephemeral dir
```

If Docker is unavailable at step 2 -> `PARTIALLY_SUPPORTED{reason="docker unavailable"}`; no host
fallback.

---

## 5. Resource limits (Spec §18) — defaults

| Limit | Default | Config key |
|---|---|---|
| CPU | 2.0 cores | `SANDBOX_CPUS` |
| Memory | 2 GiB | `SANDBOX_MEMORY_MB` |
| Memory + swap | 2 GiB (swap disabled) | `SANDBOX_MEMORY_SWAP_MB` |
| PIDs | 512 | `SANDBOX_PIDS_LIMIT` |
| Open files (`nofile`) | 4096 | `SANDBOX_ULIMIT_NOFILE` |
| Processes (`nproc`) | 512 | `SANDBOX_ULIMIT_NPROC` |
| Wall-clock per execution | 600 s | `SANDBOX_WALL_CLOCK_S` |
| Network | none | `SANDBOX_NETWORK` (`none` \| `restricted` for the deps step only) |

---

## 6. Repository & analysis limits (Spec §37)

Exceeding any -> `PARTIALLY_SUPPORTED{reason}`; partial results returned; never a crash, never
silent truncation without provenance. `core/limits.py` is the one import site that names these —
callers read `limits.analysis_seconds(settings)`, not `settings.limit_analysis_seconds`.

| Limit | Default | Setting | Enforced in | Over-limit behaviour |
|---|---|---|---|---|
| Repository size | 500 MiB | `ingestion_max_repo_bytes` | `ingestion/limits.py` | `PARTIALLY_SUPPORTED`, ingest stops |
| File count | 25 000 | `ingestion_max_files` | `ingestion/limits.py` | `PARTIALLY_SUPPORTED`, ingest stops |
| Individual file size | 2 MiB | `ingestion_max_file_bytes` | `ingestion/limits.py` | file skipped with provenance |
| Git history depth | 500 commits | `ingestion_max_history_depth` | `ingestion/limits.py` | history truncated with provenance |
| Analysis wall-clock | 300 s | `limit_analysis_seconds` | `analysis/analyze.py` | remaining files `SKIPPED`, `RepositoryAnalysis.limit_reason` set, `unknowns += analysis_incomplete` |
| Code-graph nodes | 20 000 | `limit_graph_nodes` | — (config only this phase) | *follow-up:* partial graph + provenance note |
| AI context tokens | 120 000 | `limit_ai_context_tokens` | `ai/context.py::fit_context` | lowest-priority sections dropped deterministically, provenance recorded |
| Generated tests per task | 40 | `limit_generated_tests` | `testing/` selector | newest trimmed with provenance (`testing_max_cases` is the separate hard loud-fail ceiling on one provider response) |
| Patch candidates (repair) | = repair iterations | `repair_max_iterations` | repair loop | loop exits, best-so-far kept |
| Repair iterations | 4 | `repair_max_iterations` | repair loop | as above |
| Repair wall-clock | 1200 s | `repair_wall_clock_s` | repair loop | loop exits with provenance |

---

## 6a. Deterministic AI context windowing (Spec §37)

`ai/context.py` assembles a prompt from labelled `ContextSection`s each carrying an integer
`priority` (lower = more important; **priority 0 is never dropped or truncated**). When the
estimated token count (`ceil(len(text) / 4)`, no tokeniser dependency, deliberately
over-counting) exceeds `limit_ai_context_tokens`, `fit_context`:

1. drops whole sections, **least important first**, ties broken by name (a fixed order — the same
   inputs always yield the same prompt); a dropped section's template variable becomes a visible
   `(omitted: exceeded the AI context budget)` placeholder so the render never fails;
2. as a last resort, hard-truncates the largest still-present droppable section with a
   `…[N chars omitted: AI context budget]` marker.

Every drop / truncation is returned in `FitResult.dropped` / `.truncated` and rendered to a
one-line provenance string (`FitResult.note()`); the planning and implementation services log it
against the task. Callers pass `context_budget_tokens=limits.ai_context_tokens(settings)`; the
agents default to effectively unbounded so non-service callers are unaffected.

---

## 6b. Artifact & workspace garbage collection (ADR-0009)

`retention_for(kind)` assigns each artifact a class:

| Class | Kinds | Collected |
|---|---|---|
| `PERMANENT` | `TRACE`, `PR_BODY`, `BENCHMARK` | never |
| `RETAINED` | everything else | `expires_at` (lazily backfilled to `created_at + gc_retained_days`, default 90 d) in the past |
| `EPHEMERAL` | `WORKSPACE` | owning task terminal + `gc_ephemeral_grace_s` (default 1 h); or, with no owning task, `created_at + grace` |

`orchestration/gc.py::run_gc` also sweeps `<artifacts_root>/workspaces/<id>/` directories that
have **no** artifact row pointing at them (a crashed ingest) once their mtime is older than the
grace window. It runs as a `GC` job the worker self-enqueues every `gc_interval_s` (default 1 h,
deduped on an hour-bucket key so a restart can't pile them up) and is also the
`python -m app.orchestration.gc` entrypoint for an external cron. `gc_enabled=false` disables it.

---

## 6c. Circuit breakers (`core/circuit_breaker.py`)

The AI provider (`ClaudeProvider`) and the GitHub client each route their outbound call through a
process-wide `CircuitBreaker`. After `circuit_breaker_fail_threshold` consecutive failures
(default 5) the breaker OPENs and every call fails fast with `UPSTREAM_UNAVAILABLE` (HTTP 503,
`retry_after_s`) for `circuit_breaker_reset_s` (default 30 s), then HALF_OPEN lets one probe
through (success → CLOSED, failure → OPEN). This stops a dead upstream from burning each call's
own retry budget; the fast-fail is a normal retryable job failure. 4xx "your request was wrong"
errors (GitHub 401/403/404/409) propagate **without** tripping the breaker. Open breakers are
listed by `GET /metrics`.

---

## 7. Cost & latency budget enforcement (plan §4.13)

- Per task: a cost budget (priced-model spend, `pricing-table v1.0.0`) and a wall-clock budget,
  both configurable, both checked by the Orchestrator before each phase and inside the repair
  loop.
- Exceeding a budget -> park in `AWAITING_APPROVAL` (if a human can extend it) or
  `PARTIALLY_SUPPORTED` (with partial artifacts). Never a silent overrun.
- Per-stage AI-call budgets; the Orchestrator refuses a stage that would exceed its call budget
  and records the refusal.
- Model routing (`cheap`/`frontier`), prompt caching for the repo-context prefix, deterministic
  context windowing, and the repair-loop marginal-improvement early-exit are the levers.

---

## 8. `PARTIALLY_SUPPORTED` semantics

A terminal-ish state carrying `{reason, partial_artifacts[]}`. The task is not `FAILED` (nothing
went wrong) and not `COMPLETED` (the full workflow did not run). The API and dashboard show the
reason and whatever artifacts were produced (e.g. analysis without execution when Docker is
absent). A `PARTIALLY_SUPPORTED` task can be resubmitted once the limiting condition changes.

---

## 9. Observability (Spec §24, §25)

Per task: state history, per-agent input/output/duration/errors, AI request metadata (redacted),
tool calls, test executions, patch iterations, verification results, budget consumption. Exposed
via `GET /tasks/{id}/timeline` and the dashboard. No secrets, ever.

Process-level endpoints (unauthenticated, cheap, rate-limit-exempt — like `/healthz`):

| Endpoint | Purpose |
|---|---|
| `GET /healthz` | liveness — always `{"status":"ok"}` if the process is up |
| `GET /readyz` | readiness — `200 {"status":"ready"}` when the DB answers `SELECT 1`, else `503 {"status":"not_ready", reason}` (a JSON body, not an exception, so a load balancer can drain the instance) |
| `GET /metrics` | a small operational snapshot: `queue_depth`, `jobs` (count per `JobState`), `circuit_breakers` (name / state / consecutive failures). Not Prometheus; not a metrics backend. |

---

## 10. Open questions

| # | Question | Resolution |
|---|---|---|
| E1 | asyncio worker vs arq at higher concurrency | `ADR-0003`; single sequential worker for the MVP — distributed / parallel worker is a follow-up, measured against the Phase 27 soak-shape suite |
| E2 | SQLite `SKIP LOCKED` emulation robustness | acceptable for dev/CI single-worker; PG for multi-worker |
| E3 | deps-install network policy granularity | start with an index-host allowlist; tighten in Phase 26 |
| E4 | `limit_graph_nodes` enforcement | config only in Phase 27; the partial-graph fallback in the graph builder is a follow-up |
| E5 | multi-hour soak / leak check | Phase 27 ships a fast leak-*shape* test (`tests/perf/`, `--perf`); a real N-tasks-over-M-hours soak belongs in a nightly job |
