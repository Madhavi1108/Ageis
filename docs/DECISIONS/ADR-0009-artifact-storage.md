# ADR-0009: Artifact storage

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

Spec §36 requires defining what belongs in the database vs the filesystem vs a temporary workspace
vs logs vs an artifact-storage abstraction, with cleanup, retention, reproducibility, and task
isolation.

## Decision

- An `ArtifactStore` abstraction with an `FSStore` implementation (mounted volume) for the MVP and
  an `ObjectStore` seam for later.
- `Artifact` rows (`DATA_MODEL.md` §2.5) index every blob: `kind`, `store`, `uri`, `sha256`,
  `size_bytes`, `content_type`, `retention`, `expires_at`.
- Placement rules:
  - **DB:** structured records, status, relationships, small JSON summaries.
  - **Artifact store:** patch/diff text, stdout/stderr, tracebacks, serialized graphs, reports,
    Trust Report, PR bodies.
  - **Temporary workspace:** snapshot checkout + RW copies, as `EPHEMERAL` artifacts under
    `artifacts/workspaces/`.
  - **Secrets:** never persisted anywhere.
- Retention: `EPHEMERAL` (GC'd after task terminal + grace), `RETAINED` (default 90 days),
  `PERMANENT` (Trace, PR body, Benchmark, final Patch).
- A GC job removes expired `EPHEMERAL`/`RETAINED` artifacts and orphaned workspaces; every task's
  artifacts are namespaced by `task_id` for isolation.

## Consequences

- The DB stays small and fast to back up; large data is content-addressed and dedupable.
- Reproducibility: artifacts are immutable and hash-verified.
- An outage of the artifact volume degrades the system; monitored, and the object-store seam is
  the mitigation path.

## Alternatives considered

- **Everything in the DB** — rejected by Spec §36; bloats storage and backups.
- **Object storage (S3-compatible) from day one** — rejected: infra for no MVP benefit; the seam
  is kept.
- **No retention policy** — rejected: unbounded growth; Spec §36 requires cleanup + retention.
