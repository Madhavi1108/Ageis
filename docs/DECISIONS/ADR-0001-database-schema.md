# ADR-0001: Database schema & SQLite→PostgreSQL portability

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

Specification §35 mandates a schema that works with SQLite initially and can migrate to
PostgreSQL, covering 28 named entities with proper keys, indexes, timestamps, and constraints.
Development and CI must be zero-infrastructure.

## Decision

- SQLAlchemy 2.0 models + Alembic migrations. SQLite for dev/CI, PostgreSQL-compatible schema.
- Every table: application-generated sortable UUIDv7 `id`; `created_at` / `updated_at` (timezone-
  aware, UTC); `status` where a lifecycle exists.
- FKs always declare `ondelete` (`CASCADE` owned children, `RESTRICT` must-not-dangle refs,
  `SET NULL` only where nullable by design). Index every FK plus documented hot columns.
- Natural keys get unique constraints (e.g. `RepositorySnapshot(repository_id, commit_sha)`).
- Portability rules: no `AUTOINCREMENT`; `JSON` type (→ `JSONB` on PG); enums as `String` + Python
  `Enum` (no DB-native enums); no SQLite date functions in code; partial/expression indexes via an
  Alembic PG/SQLite branch; every migration has a working `downgrade()` (CI runs up+down on
  SQLite).
- Large/generated blobs live in the artifact store via `Artifact` rows, not wide columns.
- Audit-relevant tables (`Task`, `Job`, `AuditLog`, `Verification`, `PullRequest`,
  `EngineeringMemory`) are append-or-supersede, never hard-deleted.

Full field-level design: `docs/DATA_MODEL.md`.

## Consequences

- Mechanical SQLite→PostgreSQL migration; no ORM rewrite.
- Slightly more code (manual enum validation, UUID generation) vs. leaning on DB features.
- JSON summary columns are not SQL-aggregatable; acceptable for MVP reporting.

## Alternatives considered

- **PostgreSQL from day one** — rejected: adds infra to every dev/CI run for no MVP benefit.
- **DB-native enums** — rejected: migration friction between SQLite and PG.
- **Store blobs in TEXT columns** — rejected: Spec §36 wants large artifacts outside relational
  fields; bloats the DB and backups.
