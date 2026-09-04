# ADR-0003: Job & worker model

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

Specification §19 requires separating HTTP requests from long-running analysis, with a job system
supporting IDs, status, progress, retries, cancellation, failure recovery, concurrency limits,
duplicate detection, idempotency, timestamps, and logs.

## Decision

- A DB-backed `Job` table (`DATA_MODEL.md` §2.5) is the source of truth. The API enqueues and
  returns immediately; a Worker process executes.
- **MVP worker:** in-process asyncio loop claiming jobs with `SELECT ... FOR UPDATE SKIP LOCKED`
  (emulated on SQLite via a short claim transaction). No external broker.
- Idempotency: `idempotency_key = hash(task_id, run_params)`; duplicate submit returns the
  existing job. Duplicate detection: `dedupe_key = hash(repo, normalized_issue_text)` rejected
  while an equivalent job is in flight.
- Retries: transient errors only (AI transport, sandbox infra, DB deadlock), exponential backoff,
  `max_attempts` default 2. Deterministic failures are not retried.
- Cancellation: cooperative flag checked between phases and inside the repair loop; running
  sandbox container killed.
- Crash recovery: checkpoint after every phase; a stale-heartbeat `RUNNING` job resumes from its
  checkpoint (phases are idempotent — re-running overwrites the single output row).
- Concurrency: global cap (default 4) + per-repository cap (default 1).
- The `orchestration/` package abstracts the queue so a library (arq / RQ) is a drop-in later.

## Consequences

- Zero extra infrastructure for the MVP; everything is inspectable in the DB.
- Single-process throughput ceiling; revisited in Phase 27 with soak data (open question E1).
- SKIP-LOCKED emulation on SQLite is fine for single-worker dev/CI; multi-worker needs PostgreSQL.

## Alternatives considered

- **Celery / RQ / arq from the start** — rejected: broker infra (Redis) for no MVP benefit; the
  abstraction keeps it a later swap.
- **Run analysis inside the request with a long timeout** — rejected: violates Spec §19; ties up
  API workers; no recovery.
- **Cron-polled table without SKIP LOCKED** — rejected: race conditions under concurrency.
