# ADR-0012: Repository & analysis limits

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

Spec §37 requires configurable limits for repository size, file count, file size, Git history
depth, analysis duration, generated tests, AI context, patch candidates, sandbox runtime, memory,
and CPU — and, when a limit is exceeded, a `PARTIALLY_SUPPORTED` result with a clear reason
instead of a crash.

## Decision

- All limits live in `core/limits.py` as typed config with documented defaults
  (`EXECUTION_MODEL.md` §5–§6).
- Each enforcement site checks the relevant limit and, on breach, returns/records
  `PARTIALLY_SUPPORTED{reason, partial_artifacts}` — no exception bubbling to a 500, no silent
  truncation without provenance.
- Truncation that is unavoidable (AI context) is deterministic and records exactly what was
  dropped.
- Defaults (initial): repo 500 MiB, 25 000 files, 2 MiB/file, history depth 500, analysis 300 s,
  40 generated tests, AI context = model limit − margin, patch candidates = repair iterations,
  sandbox 600 s / 2 GiB / 2 cores, repair 4 iterations / 1200 s.
- A `PARTIALLY_SUPPORTED` task is resubmittable once the limiting condition changes.

## Consequences

- Large or pathological repos degrade gracefully with a clear message; partial value is still
  delivered (e.g. analysis without execution).
- Operators can tune per deployment.
- Defaults are guesses; re-based from real data in Phase 27.

## Alternatives considered

- **Hard failure on any limit** — rejected by Spec §37.
- **No limits (best effort)** — rejected: unbounded cost, latency, and memory; a DoS surface via a
  crafted repo.
- **Silent truncation** — rejected: violates the evidence/provenance principle (Spec §21).
