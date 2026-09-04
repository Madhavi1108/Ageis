# ADR-0013: Test execution model

Status: Accepted
Date: 2026-09-04
Deciders: Phase 0

## Context

Spec §6 and §9 require intelligent test generation and execution, that a generated-but-not-executed
test never count as verified, tracking of Generated/Executed/Passed/Failed/Skipped/Invalid, and a
regression-selection mechanism with TARGETED / RELATED / REGRESSION / FULL-SUITE classes plus full
regression execution.

## Decision

- All test execution happens in the Docker sandbox (`ADR-0010`); results are parsed from pytest
  JUnit-XML / JSON into per-test outcomes.
- `TestCase.status` tracks the full lifecycle; a test with `status = GENERATED` (never `EXECUTED`)
  is explicitly **not** counted toward verification.
- Regression selection (`testing/regression.py`):
  - `TARGETED` — tests directly covering changed symbols.
  - `RELATED` — tests within k hops / same module / shared fixtures.
  - `REGRESSION` — historically-failed-in-area + high-centrality tests.
  - `FULL` — everything.
- Policy: the repair loop runs `TARGETED + RELATED`; pre-verification runs `REGRESSION` then
  `FULL` (or a documented justified subset with a risk note). Selection rationale is recorded per
  test.
- Execution outcomes: `PASS` / `FAIL` / `ERROR` / `TIMEOUT` / `OOM` / `INFRA_ERROR`.
- Coverage of changed lines is collected (coverage.py) and feeds PCS/CRS.

## Consequences

- "Never claim a test passed unless it actually executed and passed" (Spec §55 Rule 7) is
  structurally enforced.
- Full-suite runs cost time; the selection classes keep the repair loop fast without sacrificing
  the final gate.
- Repos without coverage data fall back to graph + naming heuristics at lower confidence.

## Alternatives considered

- **Always run the full suite** — rejected for the inner loop (slow); kept as the final gate.
- **Trust the model's claim that a test passes** — rejected by Spec §55 Rule 7.
- **Run tests on the host for speed** — rejected by Spec §18.
