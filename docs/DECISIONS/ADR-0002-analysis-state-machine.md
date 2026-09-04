# ADR-0002: Workflow / analysis state machine

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

Specification §19 and §36 require an explicit state machine with named states and explicit
transitions for the autonomous task pipeline, plus safe handling of partial support and human
approval.

## Decision

- A single `orchestration/state_machine.py` owns all states and a static transition table
  (`AEGIS_ARCHITECTURE.md` §6). States: `PENDING`, `QUEUED`, `INGESTING`, `ANALYZING`, `PLANNING`,
  `PLAN_VALIDATION`, `IMPLEMENTING`, `GENERATING_TESTS`, `EXECUTING_TESTS`, `INVESTIGATING`,
  `REPAIRING`, `REGRESSION_TESTING`, `REVIEWING`, `VERIFYING`, `AWAITING_APPROVAL`, `COMPLETED`,
  `FAILED`, `CANCELLED`, `PARTIALLY_SUPPORTED`.
- Every transition is a guarded function call; an undeclared transition raises and aborts the job.
- Each transition persists a `TaskStep` (with `input_ref` / `output_ref`) and an `AuditLog` entry,
  and emits a timeline event.
- `AWAITING_APPROVAL` is a first-class state entered from `PLAN_VALIDATION` (high-risk plan) or
  `VERIFYING` (policy) and resumes on a human decision.
- `PARTIALLY_SUPPORTED` is terminal-ish: carries `{reason, partial_artifacts}`, resubmittable.
- The Orchestrator, not the agents, performs transitions.

## Consequences

- Illegal states are impossible to reach silently; every task has a fully reconstructable history.
- Adding a phase = adding a state + table rows + one Orchestrator step; the invariant tests catch
  omissions.
- Slightly more ceremony per phase than ad-hoc status strings.

## Alternatives considered

- **Status string + implicit transitions** — rejected: Spec §19 demands explicit transitions; hard
  to audit.
- **A workflow-engine library (e.g. Temporal)** — rejected: heavy infra; the pipeline is linear
  with a bounded loop and fits a simple table-driven machine.
- **Per-agent local state** — rejected: violates the "Orchestrator owns state" principle
  (`ADR-0004`).
