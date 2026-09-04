# AEGIS Execution Model

Traceability: Specification §18, §19, §36, §37. Phase 0 deliverable (Spec §46 items 4, 5, 6, 15,
24, 25). Companion to `AEGIS_IMPLEMENTATION_PLAN.md` §4.3, §4.8–§4.9, §4.13; `ADR-0002`,
`ADR-0003`, `ADR-0010`, `ADR-0012`, `ADR-0013`.

Status: Accepted — 2026-09-04. Finalized (numbers tuned) in Phase 27.

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
- **Retries:** transient failures (AI transport, sandbox infra, DB deadlock) retried with
  exponential backoff up to `max_attempts` (default 2). Deterministic failures (invalid plan,
  scope violation, capability limit) are not retried.
- **Cancellation:** cooperative — a `cancel` sets a flag the Orchestrator checks between phases and
  inside the repair loop; the current sandbox container is killed and removed.
- **Crash recovery:** the Worker checkpoints `last_checkpoint` after every phase; on restart a
  `RUNNING` job with a stale `worker_id` heartbeat is resumed from its checkpoint (phases are
  designed idempotent: re-running a phase overwrites its single output row).
- **Concurrency:** a global cap (`AEGIS_MAX_CONCURRENT_JOBS`, default 4) and a per-repository cap
  (default 1) enforced by the queue; excess jobs stay `QUEUED`.
- **Worker:** MVP is an in-process asyncio worker reading the `Job` table with `SELECT ... FOR
  UPDATE SKIP LOCKED` semantics (emulated on SQLite via a short transaction + status claim). The
  `orchestration/` abstraction keeps a queue library (arq/RQ) a drop-in (`ADR-0003`).

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
silent truncation without provenance.

| Limit | Default | Config key |
|---|---|---|
| Repository size | 500 MiB | `LIMIT_REPO_BYTES` |
| File count | 25 000 | `LIMIT_FILE_COUNT` |
| Individual file size | 2 MiB | `LIMIT_FILE_BYTES` |
| Git history depth | 500 commits | `LIMIT_HISTORY_DEPTH` |
| Analysis duration | 300 s | `LIMIT_ANALYSIS_S` |
| Generated tests per task | 40 | `LIMIT_GENERATED_TESTS` |
| AI context size | model limit minus a margin | `LIMIT_AI_CONTEXT_TOKENS` |
| Patch candidates (repair) | = `max_repair_iterations` | `LIMIT_PATCH_CANDIDATES` |
| Repair iterations | 4 | `REPAIR_MAX_ITERATIONS` |
| Repair wall-clock | 1200 s | `REPAIR_WALL_CLOCK_S` |

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

---

## 10. Open questions

| # | Question | Resolution |
|---|---|---|
| E1 | asyncio worker vs arq at higher concurrency | `ADR-0003`; measured in Phase 27 soak |
| E2 | SQLite `SKIP LOCKED` emulation robustness | acceptable for dev/CI single-worker; PG for multi-worker |
| E3 | deps-install network policy granularity | start with an index-host allowlist; tighten in Phase 26 |
