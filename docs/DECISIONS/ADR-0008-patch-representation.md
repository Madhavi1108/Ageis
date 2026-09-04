# ADR-0008: Patch representation

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

Spec §3.7 requires real file modification with structured, reversible patches, a recoverable
workspace, and traceability from plan step to code change to test to verification (§3.6). §30
requires rollback and reversion to a previous candidate when a repair makes things worse.

## Decision

- The AI proposes changes as **structured edit operations**, not free-text file bodies:
  `{path, op: create|replace|insert|delete, anchor?, old?, new?, plan_step_id, rationale,
  evidence[]}`. Anchors require surrounding context lines; an ambiguous or missing anchor stops
  the agent loudly.
- Edits are applied to a **copy-on-write RW workspace** cloned from the snapshot with a baseline
  commit; the snapshot is never mutated.
- The canonical patch artifact is a **unified diff** generated from the RW workspace (`git diff`
  against the baseline). `Patch` rows store metadata + an `Artifact` pointer to the diff text.
- Every hunk links to a `plan_step_id` (`Implementation.step_trace`) for plan↔code traceability.
- Repair candidates are `Patch` rows with `is_candidate = true`; the loop keeps the best by
  `(failing_count, regression_failures, diff_size)` and auto-reverts to it on a worse attempt.
- Rollback = reset the RW workspace to the baseline (or the best candidate) commit; the original
  snapshot is always intact.

## Consequences

- Every change is reversible and independently re-appliable; deterministic replay compares diffs.
- Scope tracking is natural (touched paths vs the plan allowlist).
- Anchor-based editing can fail on churny context; the design chooses "fail loudly" over "guess".

## Alternatives considered

- **Whole-file rewrites from the model** — rejected by Spec §3.7 ("do not only produce suggested
  code"; must be minimal + reversible); high blast radius; poor diffs.
- **AST-level rewrites** — deferred: powerful but Python-specific and complex; edit-ops + diff are
  language-neutral and enough for the MVP.
- **Store patches in DB TEXT columns** — rejected: `ADR-0009` puts blobs in the artifact store.
