# AEGIS Operator Guide

Audience: whoever deploys and runs AEGIS. For submitting tasks see
[`USER_GUIDE.md`](USER_GUIDE.md); for incident playbooks see
[`RUNBOOKS.md`](RUNBOOKS.md).

Status: final — reconciled against the built system (Phases 0–28), 2026-09-09.

---

## 1. Processes

| Process | Command | Notes |
|---|---|---|
| API | `uvicorn app.main:app` (from `backend/`) | stateless; scale horizontally behind a load balancer |
| Worker | `python -m app.orchestration.worker` | **single sequential process** — one job at a time (ADR-0003). Run exactly one per database. A distributed/parallel worker is a documented follow-up. |
| GC | runs automatically as a `GC` job the worker self-enqueues every `AEGIS_GC_INTERVAL_S`; also `python -m app.orchestration.gc` for external cron | |
| Frontend | static build (`frontend/ npm run build`) served by any web server | dev: `npm run dev` on `:5173` |
| Database migrations | `alembic upgrade head` (from `backend/`) | run on deploy, before starting the API/worker |

`docker compose up` from the repo root brings up API + worker + frontend +
optional Postgres for local use (requires Docker; not exercised in CI).

## 2. Configuration

All settings are environment variables prefixed **`AEGIS_`** (or a `.env` file in
the working directory), validated eagerly at process start — a bad value fails
fast with a clear message. Source of truth: `backend/app/core/config.py`.

### Core

| Var | Default | Meaning |
|---|---|---|
| `AEGIS_ENVIRONMENT` | `dev` | `dev` \| `test` \| `prod` |
| `AEGIS_LOG_LEVEL` | `INFO` | `DEBUG`…`CRITICAL` |
| `AEGIS_DATABASE_URL` | `sqlite:///./aegis.db` | use PostgreSQL in production |
| `AEGIS_CORS_ORIGINS` | `["http://localhost:5173"]` | JSON list |
| `AEGIS_REQUEST_MAX_BODY_BYTES` | `1000000` | request body cap (411 without `Content-Length`) |
| `AEGIS_ARTIFACTS_ROOT` | `./artifacts` | blob + workspace storage root |

### AI provider

| Var | Default | Meaning |
|---|---|---|
| `AEGIS_AI_PROVIDER` | `mock` | `mock` (CI) \| `none` (rule-based fallback) \| `claude` \| `openai`/`local` (seams) |
| `AEGIS_AI_MODEL` | `claude-sonnet-5` | model id for the real provider |
| `RUN_LIVE_AI` + `ANTHROPIC_API_KEY` | unset | **not** `AEGIS_`-prefixed; required for `claude` |
| `AEGIS_AI_MAX_RETRIES` / `AEGIS_AI_RETRY_BACKOFF_S` | `2` / `0.5` | per-call transient retry |
| `AEGIS_CIRCUIT_BREAKER_FAIL_THRESHOLD` / `AEGIS_CIRCUIT_BREAKER_RESET_S` | `5` / `30` | after N consecutive AI/GitHub failures the breaker opens; calls fail fast (`UPSTREAM_UNAVAILABLE` 503) until it resets |

Per-stage timeouts / token caps: `AEGIS_AI_PLANNING_*`, `AEGIS_AI_IMPLEMENTATION_*`,
`AEGIS_AI_TEST_SYNTHESIS_*`, `AEGIS_AI_RCA_TIMEOUT_S`, `AEGIS_AI_REPAIR_*`,
`AEGIS_REVIEW_AI_*`.

### Sandbox (Spec §18)

| Var | Default | Meaning |
|---|---|---|
| `AEGIS_SANDBOX_MODE` | `docker` | `docker` (hardened) \| `fake` (local subprocess — **trusted fixtures only**) |
| `AEGIS_SANDBOX_IMAGE` / `AEGIS_SANDBOX_IMAGE_DIGEST` | `aegis-sandbox:py311` / `""` | set the digest to pin by content |
| `AEGIS_SANDBOX_CPUS` / `AEGIS_SANDBOX_MEMORY_MB` | `2.0` / `2048` | |
| `AEGIS_SANDBOX_PIDS_LIMIT` / `AEGIS_SANDBOX_NOFILE_LIMIT` / `AEGIS_SANDBOX_NPROC_LIMIT` | `512` / `4096` / `512` | |
| `AEGIS_SANDBOX_WALL_CLOCK_S` | `600` | SIGKILL on timeout |
| `AEGIS_SANDBOX_TMPFS_BYTES` | `67108864` | `/tmp` tmpfs (`noexec,nosuid,nodev`) |
| `AEGIS_SECURITY_BLOCK_UNSAFE_GENERATED_CODE` | `true` | static-scan generated test code before write/run |

Docker unavailable → executions return `PARTIALLY_SUPPORTED` (`docker unavailable`);
**there is no host fallback**.

### Repository / analysis limits (Spec §37)

| Var | Default |
|---|---|
| `AEGIS_INGESTION_MAX_REPO_BYTES` | `524288000` (500 MiB) |
| `AEGIS_INGESTION_MAX_FILES` | `25000` |
| `AEGIS_INGESTION_MAX_FILE_BYTES` | `2097152` (2 MiB) |
| `AEGIS_INGESTION_MAX_HISTORY_DEPTH` | `500` |
| `AEGIS_LIMIT_ANALYSIS_SECONDS` | `300` |
| `AEGIS_LIMIT_AI_CONTEXT_TOKENS` | `120000` |
| `AEGIS_LIMIT_GENERATED_TESTS` | `40` |
| `AEGIS_LIMIT_GRAPH_NODES` | `20000` (config only — no partial-graph fallback yet) |

`AEGIS_INGESTION_LOCAL_ROOTS` (JSON list) whitelists the directories a `LOCAL`
repo may be ingested from; `AEGIS_INGESTION_ALLOWED_REMOTE_HOSTS` does the same
for clone URLs (SSRF guard).

### Repair / verification / scoring

`AEGIS_REPAIR_MAX_ITERATIONS` (`4`), `AEGIS_REPAIR_WALL_CLOCK_S` (`1200`),
`AEGIS_REPAIR_MIN_IMPROVEMENT` (`1`); `AEGIS_VERIFICATION_PCS_MIN` (`70`),
`AEGIS_VERIFICATION_CRS_MAX` (`49`) — a result outside these lands the task in
`AWAITING_APPROVAL`.

### Git / GitHub

`AEGIS_GITHUB_TOKEN` (the only secret-typed field; never logged),
`AEGIS_GITHUB_API_BASE_URL`, `AEGIS_GITHUB_TIMEOUT_S`, `AEGIS_GITHUB_MAX_RETRIES`,
`AEGIS_GITHUB_PROTECTED_BRANCHES` (`["main","master"]` — a PR against one needs an
explicit approval flag), `AEGIS_GIT_PR_BRANCH_PREFIX` (`aegis/`).
`AEGIS_ORCHESTRATOR_OPEN_PR` (`false`) must be on for the orchestrator to open a
real PR.

### Job worker & reliability

`AEGIS_WORKER_POLL_INTERVAL_S` (`1.0`), `AEGIS_WORKER_STALE_AFTER_S` (`900` — a
`RUNNING` job with no heartbeat past this is reclaimed), `AEGIS_JOB_BACKOFF_BASE_S`
(`2.0`), `AEGIS_JOB_MAX_ATTEMPTS` (`2`), `AEGIS_JOB_MAX_QUEUE_DEPTH` (`100` — new
runs get `JOB_QUEUE_FULL` 429 above this).

### Garbage collection / retention (ADR-0009)

`AEGIS_GC_ENABLED` (`true`), `AEGIS_GC_INTERVAL_S` (`3600`),
`AEGIS_GC_EPHEMERAL_GRACE_S` (`3600` — workspace kept this long after the task is
terminal), `AEGIS_GC_RETAINED_DAYS` (`90`). `TRACE` / `PR_BODY` / `BENCHMARK`
artifacts are `PERMANENT` and never collected.

### Auth & rate limiting (both opt-in)

`AEGIS_AUTH_ENABLED` (`false`) + `AEGIS_API_KEYS` (`{"<key>": "<role>"}`, role ∈
viewer / operator / approver / admin). With auth off, mutating routes declare a
role but the check is a no-op. `AEGIS_RATE_LIMIT_ENABLED` (`false`),
`AEGIS_RATE_LIMIT_PER_MINUTE` (`120`), `AEGIS_RATE_LIMIT_BURST` (`20`);
`/`, `/healthz`, `/readyz`, `/metrics`, `/version` are exempt.

### Memory (opt-in)

`AEGIS_MEMORY_ENABLED` (`false`). When on, terminal-state tasks are written to
engineering memory and retrieval hooks feed "historical — verify" evidence to
mapping / planning / regression. Never auto-applies a patch.

## 3. Health, readiness, metrics

| Endpoint | Use |
|---|---|
| `GET /healthz` | liveness — process is up |
| `GET /readyz` | readiness — DB answers `SELECT 1`; `503` otherwise (drain the instance) |
| `GET /metrics` | JSON: `queue_depth`, `jobs` (count per state), `circuit_breakers` (name/state/consecutive failures). Not Prometheus. |
| `GET /version` | build metadata |

Point the load balancer's health check at `/readyz`. Alert on: `queue_depth`
near `AEGIS_JOB_MAX_QUEUE_DEPTH`, any circuit breaker `OPEN`, `jobs.FAILED`
climbing, `/readyz` non-200.

## 4. Logging

JSON lines on stdout: `timestamp`, `level`, `logger`, `message`, `correlation_id`
(per-request). Secret shapes (tokens, keys, `Authorization` headers) are redacted
by `app/core/security/redaction.py` before anything is written — including inside
AI and GitHub call logs. Ship stdout to your log aggregator; do not enable
`DEBUG` in `prod` (verbose prompt/response metadata).

## 5. Database & backups

SQLite is the dev/CI default and is single-writer — fine with the single
sequential worker, not for multi-instance. For production use PostgreSQL
(`AEGIS_DATABASE_URL=postgresql+psycopg://…`) and run `alembic upgrade head` on
deploy. Back up the database and `AEGIS_ARTIFACTS_ROOT` together — artifact rows
point at files under that root. The migration chain is linear (`0001`…`0021`);
`alembic downgrade` is supported for rollback.

## 6. The sandbox image

Build `docker/sandbox.Dockerfile` → tag it `aegis-sandbox:py311` (or set
`AEGIS_SANDBOX_IMAGE`). For supply-chain pinning, resolve its digest and set
`AEGIS_SANDBOX_IMAGE_DIGEST`. There is no image registry / publish pipeline yet
(documented open item, ADR-0010).
