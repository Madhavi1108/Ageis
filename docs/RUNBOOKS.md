# AEGIS Runbooks

Incident playbooks for operators. Config reference and process list are in
[`OPERATOR_GUIDE.md`](OPERATOR_GUIDE.md).

Status: final — reconciled against the built system (Phases 0–28), 2026-09-09.

Every playbook: **Symptom → Check → Action.**

---

## 1. AI provider outage (circuit breaker OPEN)

- **Symptom:** tasks fail or park with `UPSTREAM_UNAVAILABLE` (503); `GET /metrics`
  shows a circuit breaker `state: OPEN` for `ai`.
- **Check:** provider status page / API key validity / quota. `grep` the JSON
  logs for `logger: app.ai...` `outcome: transport_error`. The breaker opens
  after `AEGIS_CIRCUIT_BREAKER_FAIL_THRESHOLD` (5) consecutive failures and
  half-opens after `AEGIS_CIRCUIT_BREAKER_RESET_S` (30 s).
- **Action:** if the upstream is healthy again, no action — the next probe closes
  the breaker and the job's own retry/backoff resumes it. If the outage is
  prolonged, either pause intake (`AEGIS_JOB_MAX_QUEUE_DEPTH=0`-ish is not
  supported; instead stop the worker) or switch `AEGIS_AI_PROVIDER=none` to run
  the deterministic rule-based fallback (lower quality, clearly labelled). Failed
  jobs are retryable — re-run them once the provider is back.

## 2. Sandbox / Docker unavailable

- **Symptom:** executions return `PARTIALLY_SUPPORTED` with reason
  `docker unavailable: …`; tasks reach `PARTIALLY_SUPPORTED` after analysis/plan.
- **Check:** `docker version` on the worker host; the daemon socket permissions;
  `AEGIS_SANDBOX_IMAGE` exists (`docker image inspect aegis-sandbox:py311`).
- **Action:** restore the daemon / rebuild the image (`docker build -f
  docker/sandbox.Dockerfile`). **Never** set `AEGIS_SANDBOX_MODE=fake` in
  production — `fake` runs tests as a host subprocess and is for trusted fixtures
  only. Re-run the affected tasks; there is no host fallback by design (ADR-0010).

## 3. Job queue full (`JOB_QUEUE_FULL` 429s)

- **Symptom:** `POST /tasks/{id}/run` returns 429 `JOB_QUEUE_FULL`; `GET /metrics`
  `queue_depth` at `AEGIS_JOB_MAX_QUEUE_DEPTH` (100).
- **Check:** is the worker running and making progress? `GET /metrics` →
  `jobs.RUNNING` should be 1 and advancing; `jobs.FAILED` not spiking. Look for a
  stuck job (next playbook).
- **Action:** the worker is single-threaded, so depth clears at the rate one task
  completes — this is backpressure working as designed. If load is legitimately
  high, raise `AEGIS_JOB_MAX_QUEUE_DEPTH` and provision a faster host; a
  parallel/distributed worker is a known follow-up, not yet available. If the
  queue is full because a job is stuck, fix that first.

## 4. Stuck / orphaned job

- **Symptom:** a job sits in `RUNNING` far longer than a task should take; the
  timeline hasn't advanced.
- **Check:** `GET /jobs/{id}` — `heartbeat_at` should refresh every stage. If the
  worker process died, the job's `heartbeat_at` is stale.
- **Action:** the worker auto-reclaims a `RUNNING` job whose heartbeat is older
  than `AEGIS_WORKER_STALE_AFTER_S` (900 s) and resumes it from
  `last_checkpoint`. If it is genuinely wedged (e.g. an external hang), stop the
  worker, `POST /jobs/{id}/cancel`, restart the worker. Phases are idempotent —
  a resumed job overwrites its stage output, it does not double-apply.

## 5. Disk pressure / GC not keeping up

- **Symptom:** `AEGIS_ARTIFACTS_ROOT` filesystem filling; many
  `…/workspaces/<id>/` directories.
- **Check:** `AEGIS_GC_ENABLED=true`? Is a `GC` job running each
  `AEGIS_GC_INTERVAL_S` (`GET /jobs?type=GC`)? EPHEMERAL workspaces are only
  collected once the owning task is terminal + `AEGIS_GC_EPHEMERAL_GRACE_S`.
- **Action:** run it now — `python -m app.orchestration.gc` (prints a summary).
  Lower `AEGIS_GC_EPHEMERAL_GRACE_S` / `AEGIS_GC_RETAINED_DAYS` if retention is
  too generous. `TRACE` / `PR_BODY` / `BENCHMARK` artifacts are `PERMANENT` by
  design — archive them off-box if space is tight.

## 6. Migration failure on deploy

- **Symptom:** `alembic upgrade head` errors; API/worker won't start (config +
  schema are validated eagerly).
- **Check:** current revision (`alembic current`) vs. `head`; the failing
  revision's `upgrade()`; DB user privileges; for SQLite, a stale/locked file.
- **Action:** fix forward if possible. To roll back: `alembic downgrade -1` (the
  chain supports it) and redeploy the previous release. Restore the DB + artifacts
  backup together if the migration partially applied. Never edit a committed
  migration that has run anywhere — add a new one.

## 7. Secret suspected in logs or an artifact

- **Symptom:** a token-shaped string appears in a log line or a stored artifact.
- **Check:** `app/core/security/redaction.py` redacts known secret shapes before
  write; a leak means an unrecognised shape. Identify the source field.
- **Action:** rotate the credential immediately. Purge the affected log
  lines / artifacts. Add the shape to the redaction patterns and its regression
  test (`backend/tests/security/test_secret_scan.py`). `AEGIS_GITHUB_TOKEN` is
  `SecretStr` and only read when a client is built — check nothing logs the
  settings object.

## 8. Task keeps landing in `AWAITING_APPROVAL`

- **Symptom:** verified changes still park for a human.
- **Check:** the verification verdict on `GET /tasks/{id}/verification` — a
  `PARTIAL` verdict means PCS `< AEGIS_VERIFICATION_PCS_MIN` (70) or CRS `>
  AEGIS_VERIFICATION_CRS_MAX` (49), or a mandatory criterion is unmet.
- **Action:** this is the human-in-the-loop safety gate working. If your risk
  tolerance is higher, adjust the thresholds — but that weakens the wedge
  (auditable, low-false-complete autonomy). Approvals are audited.
