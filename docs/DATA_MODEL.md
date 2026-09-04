# AEGIS Data Model

Traceability: Specification §35, §36. Phase 0 deliverable (Spec §46 item 3). Companion to
`AEGIS_IMPLEMENTATION_PLAN.md` §4.4 and `ADR-0001`.

Status: Accepted — 2026-09-04. Field lists are the design intent; exact column types are finalized
with the first Alembic migration in Phase 2.

---

## 1. Principles

- **SQLite (dev) with a PostgreSQL-compatible schema.** No SQLite-only types. Booleans as
  `Boolean`, timestamps as timezone-aware `DateTime` stored UTC, JSON as `JSON` (maps to
  `JSONB` on PG), enums as `String` + a Python `Enum` (portable; DB-native enums avoided).
- **Every table:** surrogate primary key `id` (UUIDv7-style, sortable, stored as string/uuid);
  `created_at`, `updated_at` (UTC, server default + onupdate); a `status` column where a lifecycle
  exists.
- **Foreign keys:** always with an explicit `ondelete` (`CASCADE` for owned children, `RESTRICT`
  for references that must not dangle, `SET NULL` only where the column is nullable by design).
- **Indexes:** on every FK column; plus the common query columns called out per table below.
- **Uniqueness:** natural keys get a unique constraint (listed per table).
- **Large / generated blobs** (patch text, logs, serialized graphs, reports, workspaces) do **not**
  live in wide columns — they are `Artifact` rows pointing at the artifact store (see §4).
- **No hard deletes of audit-relevant rows.** `Task`, `Job`, `AuditLog`, `Verification`,
  `PullRequest`, `EngineeringMemory` are append-or-supersede, never deleted.

---

## 2. Entities (28)

Grouped by lifecycle stage. Each entry: key fields, FKs, indexes, unique constraints, enums.

### 2.1 Repository ingestion & intelligence

**Repository** — a target repo AEGIS has been pointed at.
- `id`, `source_type` enum(`LOCAL`,`GITHUB`), `url_or_path` (redaction-safe; no embedded creds),
  `default_branch`, `name`, `owner` (nullable), `created_at`, `updated_at`.
- Unique: (`source_type`, `url_or_path`).
- Index: `name`.

**RepositorySnapshot** — an immutable checkout at one commit.
- `id`, `repository_id` -> Repository (`CASCADE`), `commit_sha`, `branch`, `ingested_at`,
  `file_count`, `total_bytes`, `history_depth`, `languages` (JSON: {lang: file_count}),
  `status` enum(`INGESTING`,`READY`,`PARTIALLY_SUPPORTED`,`FAILED`), `limit_reason` (nullable).
- Unique: (`repository_id`, `commit_sha`).
- Index: `repository_id`, `status`.

**RepositoryFile** — one file in a snapshot.
- `id`, `snapshot_id` -> RepositorySnapshot (`CASCADE`), `path`, `size_bytes`, `sha256`,
  `language`, `is_test` (bool), `is_vendored` (bool), `parse_status`
  enum(`OK`,`SYNTAX_ERROR`,`SKIPPED`), `parse_error` (nullable).
- Unique: (`snapshot_id`, `path`).
- Index: (`snapshot_id`, `path`), (`snapshot_id`, `is_test`), `language`.

**RepositorySymbol** — a function / class / method / module-level symbol.
- `id`, `snapshot_id` -> (`CASCADE`), `file_id` -> RepositoryFile (`CASCADE`),
  `symbol_id` (`"{relpath}::{qualname}"`), `kind` enum(`MODULE`,`CLASS`,`FUNCTION`,`METHOD`),
  `qualname`, `signature`, `lineno`, `end_lineno`, `decorators` (JSON), `docstring` (nullable),
  `is_exported` (bool).
- Unique: (`snapshot_id`, `symbol_id`).
- Index: (`snapshot_id`, `symbol_id`), (`file_id`), (`snapshot_id`, `kind`).

**Dependency** — an import edge or a third-party package requirement.
- `id`, `snapshot_id` -> (`CASCADE`), `kind` enum(`IMPORT`,`PACKAGE`),
  `from_file_id` (nullable) -> RepositoryFile (`CASCADE`), `target` (module or package name),
  `classification` enum(`STDLIB`,`THIRD_PARTY`,`LOCAL`,`UNKNOWN`), `version_spec` (nullable),
  `extras` (JSON, nullable).
- Index: (`snapshot_id`, `classification`), (`from_file_id`).

**Commit** — a Git commit relevant to analysis / history intelligence.
- `id`, `repository_id` -> (`CASCADE`), `sha`, `authored_at`, `author_email_hash`
  (hashed, not raw), `message`, `files_changed` (JSON: [path]), `insertions`, `deletions`,
  `is_related_fix` (bool, set by Git intelligence).
- Unique: (`repository_id`, `sha`).
- Index: `repository_id`, `authored_at`.

**RepositoryAnalysis** — the assembled `RepositoryContext` for a snapshot.
- `id`, `snapshot_id` -> (`CASCADE`), `entry_points` (JSON), `test_framework` (nullable),
  `test_command` (nullable), `package_manager` (nullable), `build_backend` (nullable),
  `graph_artifact_id` -> Artifact (`SET NULL`), `summary` (JSON), `unknowns` (JSON list),
  `analysed_at`, `duration_ms`.
- Unique: (`snapshot_id`).

### 2.2 Task & planning

**Issue** — a normalized external issue (may back a Task).
- `id`, `repository_id` -> (`RESTRICT`), `source` enum(`API`,`GITHUB`,`EXCEL`),
  `external_ref` (nullable, e.g. GH issue number), `title`, `body_sanitized`,
  `imported_at`.
- Index: `repository_id`, (`source`, `external_ref`).

**Task** — a unit of engineering work.
- `id`, `repository_id` -> (`RESTRICT`), `issue_id` (nullable) -> Issue (`SET NULL`),
  `snapshot_id` (nullable, set at ingestion) -> RepositorySnapshot (`RESTRICT`),
  `task_type` enum(`BUG`,`FEATURE`,`REFACTOR`,`REQUIREMENT`,`QUESTION`),
  `title`, `description_sanitized`, `constraints` (JSON), `priority` enum(`LOW`,`NORMAL`,`HIGH`),
  `allowed_paths` (JSON, nullable — scope allowlist), `idempotency_key` (hash of repo+normalized
  text), `state` enum(all workflow states), `terminal_reason` (nullable),
  `created_by` (subject id), `created_at`, `updated_at`.
- Unique: (`repository_id`, `idempotency_key`).
- Index: `state`, `repository_id`, `created_at`.

**TaskStep** — one workflow-state entry in a task's timeline.
- `id`, `task_id` -> Task (`CASCADE`), `seq` (int), `state`, `entered_at`, `exited_at` (nullable),
  `agent` (nullable), `input_ref` (nullable Artifact/row ref), `output_ref` (nullable),
  `error` (JSON, nullable), `duration_ms` (nullable).
- Unique: (`task_id`, `seq`).
- Index: (`task_id`, `seq`), (`task_id`, `state`).

**CodeMapping** — the `IssueCodeMapping` result.
- `id`, `task_id` -> (`CASCADE`), `candidates` (JSON: [{path, symbols[], score, confidence,
  labels[], evidence[]}]), `related_tests` (JSON), `dependencies` (JSON), `overall_confidence`,
  `model_version` (`mapping-model vX`), `created_at`.
- Unique: (`task_id`).

**ImpactAnalysis** — the `ImpactAnalysis` result.
- `id`, `task_id` -> (`CASCADE`), `changed_set` (JSON), `blast_radius` (JSON by hop),
  `callers` (JSON), `related_tests` (JSON), `public_api_touched` (JSON),
  `config_refs` (JSON), `db_refs` (JSON, labelled INFERENCE), `regression_areas` (JSON),
  `risk_signal_bundle` (JSON), `created_at`.
- Unique: (`task_id`).

**EngineeringPlan** — the validated plan.
- `id`, `task_id` -> (`CASCADE`), `version` (int, increments on REVISE), `problem_interpretation`,
  `assumptions` (JSON), `files_to_inspect` (JSON), `files_to_modify` (JSON),
  `symbols_to_modify` (JSON), `dependencies` (JSON), `steps` (JSON: [{id, description,
  test_intent, evidence_refs}]), `test_strategy` (JSON), `expected_behavior`,
  `regression_risks` (JSON), `rollback_strategy`, `confidence`, `source`
  enum(`AI`,`RULE_BASED_FALLBACK`), `created_at`.
- Unique: (`task_id`, `version`).

**Implementation** — the applied change set for a plan.
- `id`, `task_id` -> (`CASCADE`), `plan_id` -> EngineeringPlan (`RESTRICT`),
  `patch_id` -> Patch (`RESTRICT`), `step_trace` (JSON: [{plan_step_id, file, hunk_ref,
  rationale, evidence}]), `scope_violations` (JSON), `created_at`.
- Unique: (`task_id`, `plan_id`).

**Patch** — a reversible unified diff (text in the artifact store).
- `id`, `task_id` -> (`CASCADE`), `artifact_id` -> Artifact (`RESTRICT`),
  `base_commit_sha`, `files_changed` (JSON), `additions`, `deletions`, `applies_clean` (bool),
  `is_candidate` (bool — repair candidate vs final), `created_at`.
- Index: (`task_id`, `is_candidate`).

### 2.3 Testing, failure, repair

**TestCase** — a generated or selected test.
- `id`, `task_id` -> (`CASCADE`), `name`, `path`, `target_symbol` (nullable),
  `kind` enum(`EDGE`,`NEGATIVE`,`BOUNDARY`,`REGRESSION`,`ISSUE`,`EXISTING`),
  `origin` enum(`GENERATED`,`EXISTING`), `rationale`, `evidence` (JSON),
  `status` enum(`GENERATED`,`EXECUTED`,`PASSED`,`FAILED`,`SKIPPED`,`INVALID`).
- Index: (`task_id`, `status`), (`task_id`, `kind`).

**TestExecution** — one sandbox run of a set of tests.
- `id`, `task_id` -> (`CASCADE`), `selection` enum(`TARGETED`,`RELATED`,`REGRESSION`,`FULL`),
  `command`, `exit_code`, `started_at`, `finished_at`, `duration_ms`,
  `results` (JSON: [{test_id, outcome, duration_ms}]), `stdout_artifact_id` -> Artifact
  (`SET NULL`), `stderr_artifact_id` -> Artifact (`SET NULL`),
  `resource_usage` (JSON: {cpu_s, max_rss_mb, wall_ms}),
  `outcome` enum(`PASS`,`FAIL`,`ERROR`,`TIMEOUT`,`OOM`,`INFRA_ERROR`),
  `repair_attempt_id` (nullable) -> RepairAttempt (`SET NULL`).
- Index: (`task_id`, `selection`), (`task_id`, `outcome`).

**Failure** — a single failing test / error captured from an execution.
- `id`, `execution_id` -> TestExecution (`CASCADE`), `task_id` -> (`CASCADE`),
  `test_name`, `failure_type` enum(`ASSERTION`,`EXCEPTION`,`COLLECTION_ERROR`,`TIMEOUT`,
  `IMPORT_ERROR`,`ENV`), `traceback_artifact_id` -> Artifact (`SET NULL`),
  `frames` (JSON: [{file, lineno, symbol_id, in_diff}]), `created_at`.
- Index: (`task_id`), (`execution_id`).

**Investigation** — the `FailureAnalysis` bundle for a failure set.
- `id`, `task_id` -> (`CASCADE`), `failure_ids` (JSON), `evidence` (JSON: code slices, diff hunks,
  related tests, recent commits), `facts` (JSON), `inferences` (JSON), `classification` (JSON),
  `created_at`.
- Index: (`task_id`).

**RepairAttempt** — one bounded repair iteration.
- `id`, `task_id` -> (`CASCADE`), `iteration` (int), `root_cause` (JSON: RCA with FACT/INFERENCE/
  HYPOTHESIS split + evidence), `proposal` (JSON: RepairProposal), `candidate_patch_id`
  (nullable) -> Patch (`SET NULL`), `targeted_execution_id` (nullable) -> TestExecution
  (`SET NULL`), `regression_execution_id` (nullable) -> TestExecution (`SET NULL`),
  `outcome` enum(`IMPROVED`,`NO_CHANGE`,`WORSENED`,`GREEN`,`REVERTED`),
  `score` (JSON: {failing_count, regression_failures, diff_size}), `created_at`.
- Unique: (`task_id`, `iteration`).

### 2.4 Review, risk, verification, delivery

**ReviewFinding** — one automated-review finding.
- `id`, `task_id` -> (`CASCADE`), `source` enum(`STATIC`,`AI`,`RULE`),
  `category` enum(`CORRECTNESS`,`SCOPE`,`SECURITY`,`MAINTAINABILITY`,`ARCHITECTURE`,`PERFORMANCE`,
  `ERROR_HANDLING`,`TEST_QUALITY`,`REGRESSION_RISK`,`DEPENDENCY_IMPACT`),
  `severity` enum(`CRITICAL`,`HIGH`,`MEDIUM`,`LOW`,`INFO`), `file` (nullable), `line_start`
  (nullable), `line_end` (nullable), `description`, `evidence` (JSON), `recommendation`,
  `confidence`, `status` enum(`OPEN`,`RESOLVED`,`OVERRIDDEN`), `created_at`.
- Index: (`task_id`, `severity`), (`task_id`, `category`), (`task_id`, `status`).

**RiskAssessment** — a PCS + CRS + Task-Specific Risk Profile snapshot.
- `id`, `task_id` -> (`CASCADE`), `patch_id` -> Patch (`RESTRICT`),
  `pcs_value`, `pcs_classification`, `pcs_breakdown` (JSON: signal -> contribution),
  `crs_value`, `crs_classification`, `crs_breakdown` (JSON),
  `task_risk_profile` (JSON), `hard_gate` (nullable enum: which gate forced BLOCKED),
  `model_version` (`scoring-model vX`), `created_at`.
- Index: (`task_id`), (`patch_id`).

**Verification** — the completion verdict.
- `id`, `task_id` -> (`CASCADE`), `verdict` enum(`VERIFIED`,`NOT_VERIFIED`,`PARTIAL`),
  `criteria` (JSON: [{name, verdict, evidence}]), `plan_alignment` (JSON),
  `trace_artifact_id` -> Artifact (`RESTRICT`), `replay_fidelity` (nullable float),
  `confidence`, `created_at`.
- Unique: (`task_id`) — one live verification; supersede via a new row + `superseded_by` link
  (nullable self-FK).

**PullRequest** — a generated PR artifact and/or a real GitHub PR.
- `id`, `task_id` -> (`CASCADE`), `mode` enum(`LOCAL_ARTIFACT`,`GITHUB`),
  `title`, `body_artifact_id` -> Artifact (`RESTRICT`), `branch` (nullable),
  `commit_sha` (nullable), `github_url` (nullable), `github_number` (nullable),
  `state` enum(`DRAFTED`,`CREATED`,`FAILED`), `failure_reason` (nullable), `created_at`.
- Index: (`task_id`), (`state`).

**EngineeringMemory** — a persisted completed-task record for future retrieval.
- `id`, `repository_id` -> (`RESTRICT`), `task_id` -> Task (`RESTRICT`),
  `issue_text_sanitized`, `touched_symbols` (JSON), `failure_signatures` (JSON),
  `fix_summary`, `plan_ref` (JSON snapshot), `patch_ref` (Artifact id),
  `review_summary` (JSON), `verification_verdict`, `outcome` enum(`VERIFIED`,`SAFE_STOP`),
  `embedding_ref` (nullable), `created_at`.
- Index: `repository_id`, `created_at`; FTS index on `issue_text_sanitized` + `fix_summary`.

### 2.5 Platform

**Job** — an async unit of work driving a task run.
- `id`, `task_id` -> Task (`CASCADE`), `type` enum(`INGEST`,`RUN_TASK`,`BENCHMARK`,`GC`),
  `state` enum(`PENDING`,`QUEUED`,`RUNNING`,`SUCCEEDED`,`FAILED`,`CANCELLED`),
  `progress` (0..1), `attempts` (int), `max_attempts` (int), `idempotency_key`,
  `dedupe_key` (nullable), `last_checkpoint` (JSON: {phase, cursor}), `worker_id` (nullable),
  `queued_at`, `started_at` (nullable), `finished_at` (nullable), `error` (JSON, nullable),
  `logs_artifact_id` -> Artifact (`SET NULL`).
- Unique: (`idempotency_key`); partial-unique on `dedupe_key` where `state IN (PENDING,QUEUED,
  RUNNING)`.
- Index: `state`, `task_id`, `queued_at`.

**Artifact** — a pointer to a stored blob.
- `id`, `task_id` (nullable) -> Task (`CASCADE`), `snapshot_id` (nullable) -> RepositorySnapshot
  (`CASCADE`), `kind` enum(`PATCH`,`DIFF`,`LOG`,`GRAPH`,`REPORT`,`TRACE`,`WORKSPACE`,`STDIO`,
  `PR_BODY`,`BENCHMARK`), `store` enum(`FS`,`OBJECT`), `uri`, `sha256`, `size_bytes`,
  `content_type`, `retention` enum(`EPHEMERAL`,`RETAINED`,`PERMANENT`), `expires_at` (nullable),
  `created_at`.
- Index: (`task_id`, `kind`), `retention`, `expires_at`.

**AuditLog** — tamper-evident record of every mutating / autonomous action.
- `id`, `seq` (monotonic per chain), `task_id` (nullable) -> Task (`SET NULL`),
  `actor` (subject id or `SYSTEM`/`AGENT:<name>`), `action`, `target_type`, `target_id`
  (nullable), `payload_digest` (sha256 of redacted payload), `prev_hash`, `entry_hash`
  (= sha256(`seq || prev_hash || actor || action || target_type || target_id || payload_digest ||
  created_at`)), `created_at`.
- Unique: (`seq`). Append-only; no update, no delete. See `GOVERNANCE.md`.

---

## 3. Relationship overview

```
Repository 1--* RepositorySnapshot 1--* RepositoryFile 1--* RepositorySymbol
Repository 1--* Commit
RepositorySnapshot 1--1 RepositoryAnalysis
RepositorySnapshot 1--* Dependency
Repository 1--* Issue ;  Repository 1--* Task ;  Issue 1--* Task
Task 1--* TaskStep
Task 1--1 CodeMapping ;  Task 1--1 ImpactAnalysis
Task 1--* EngineeringPlan 1--1 Implementation 1--1 Patch
Task 1--* TestCase ;  Task 1--* TestExecution 1--* Failure
Task 1--* Investigation ;  Task 1--* RepairAttempt
Task 1--* ReviewFinding ;  Task 1--* RiskAssessment
Task 1--1 Verification (supersede chain)
Task 1--* PullRequest
Task 1--1 EngineeringMemory (on terminal)
Task 1--* Job ;  Task 1--* Artifact
AuditLog : global hash-chain, optional task_id
```

---

## 4. DB vs artifact store vs workspace (Spec §36)

| Data | Where |
|---|---|
| Structured records, status, relationships, small JSON summaries | **Database** |
| Patch/diff text, stdout/stderr, tracebacks, serialized graphs, reports, Trust Report, PR body | **Artifact store** (`Artifact` row + `FS`/`OBJECT` blob) |
| Checked-out repo, RW copy for edits | **Temporary workspace** (`artifacts/workspaces/<snapshot|task>`), `Artifact(kind=WORKSPACE, retention=EPHEMERAL)` |
| Secrets / tokens | **Never persisted.** Config + process env only; redacted everywhere else |

Retention: `EPHEMERAL` artifacts GC'd after the task terminates + a grace window; `RETAINED` kept
per policy (default 90 days); `PERMANENT` for Trace, PR body, Benchmark, and the final Patch.

---

## 5. Portability rules (SQLite -> PostgreSQL)

- Timezone-aware `DateTime`, always UTC; no `datetime('now')` SQLite functions in code.
- `JSON` column type (SQLAlchemy) — becomes `JSONB` on PG.
- No `AUTOINCREMENT`; ids are application-generated UUIDv7.
- Enums as `String(length)` + Python `Enum`, validated at the model layer.
- Partial/expression indexes (e.g. Job `dedupe_key`) written via Alembic with a PG/SQLite branch.
- Every migration has a working `downgrade()`; a CI job runs `upgrade` then `downgrade` on SQLite.

---

## 6. Open questions

| # | Question | Resolution |
|---|---|---|
| D1 | store `pcs_breakdown` / `crs_breakdown` as columns vs JSON | JSON for MVP; revisit if reporting needs SQL aggregation |
| D2 | one `Verification` row + supersede vs history table | supersede chain via self-FK; sufficient and simple |
| D3 | `author_email_hash` salt management | per-repository salt stored with the Repository row; documented in `GOVERNANCE.md` |
