# AEGIS Acceptance Scenarios

Traceability: Specification §39 (the 18-step workflow). Phase 24 deliverable. Companion to
`AEGIS_IMPLEMENTATION_PLAN.md` §32, §5.5; driven by `backend/tests/e2e/test_full_pipeline.py`.

Status: Accepted — 2026-09-08.

---

## 1. The controlled repository

`test-repositories/aegis-acceptance/` is a minimal billing / checkout application. It is plain
files on disk (no committed `.git`) so the ~20 per-stage `*_acceptance_fixture.py` integration
tests can point at it directly; the **crafted Git history** is replayed into a throwaway
directory at test time by `backend/tests/e2e/_acceptance_repo.py`
(`scripts/build_acceptance_repo.py` is a convenience wrapper). The replayed working tree is
byte-identical to the on-disk fixture.

| File | Role |
|---|---|
| `invoice.py` | `calculate_total(price, discount)` — **the seeded bug**: the docstring says a discount above `0.5` must be capped; the code does not cap it. |
| `config.py` | `MAX_DISCOUNT = 0.5` — the "configured maximum" the fix should honour. |
| `checkout.py` | `process_checkout()` → `from invoice import calculate_total` (imported-name call path). |
| `order_service.py` | `finalize_order()` → `import invoice` + `invoice.calculate_total(...)` (attribute call path). |
| `utils.py` | `format_currency()` — a distractor for issue→code localization. |
| `test_invoice.py` | `test_no_discount` (passes) and `test_discount_capped_at_50_percent` (**fails** — the reproducible bug). |
| `task.md` | Scenario A seed (bug fix + boundary validation). |
| `task_feature.md` | Scenario B seed (feature: order-level tax). |

`test-repositories/aegis-acceptance-unfixable/` is the scenario C variant: `rounding.py`
(`round_half_away()` delegating to banker's `round()`), `test_rounding.py`, `task.md`.

### Nine required properties

| # | Property | Where |
|---|---|---|
| 1 | Multiple Python modules | `invoice`, `checkout`, `order_service`, `config`, `utils` |
| 2 | Dependency relationships | `checkout` + `order_service` both import `invoice` (two call-resolution paths) |
| 3 | Existing tests | `test_invoice.py` |
| 4 | Intentionally incomplete behaviour | `calculate_total` ignores the discount cap |
| 5 | ≥1 reproducible bug | `test_discount_capped_at_50_percent` fails on the raw fixture |
| 6 | ≥1 feature request | `task_feature.md` (scenario B) |
| 7 | Test gaps | no tests for `checkout.py` / `order_service.py` |
| 8 | Realistic architecture | logic modules + a separate `config` module + a callers graph |
| 9 | Real Git history | four crafted commits (below), replayed at test time |

Asserted by `backend/tests/unit/test_acceptance_fixture_integrity.py`.

## 2. Crafted Git history

Replayed by `build_acceptance_git_repo()`. Four commits, distinct authors, increasing dates:

1. **Initial billing skeleton** — `invoice.py` (an earlier `price - price*discount` formulation),
   `checkout.py`.
2. **Add order finalization and currency helpers** — `order_service.py`, `utils.py`,
   `test_invoice.py` (only `test_no_discount`).
3. **Fix rounding drift in calculate_total() discount math** — rewrites `invoice.py` to the
   canonical `price * (1 - discount)` body. **This is the "prior related fix"**: it touched
   `calculate_total` before, so `git blame` on the return line and the churn/`related_fixes`
   signals point Git intelligence (Phase 19) and engineering memory (Phase 20) at it when
   localizing scenario A.
4. **Add MAX_DISCOUNT config and a boundary test for the discount cap** — adds `config.py`,
   `task.md`, `task_feature.md`, and the known-failing `test_discount_capped_at_50_percent`.

## 3. Scenarios

Canned deterministic `MockProvider` answers live in `backend/tests/e2e/_acceptance_scenarios.py`
(keyed by task id); gold expectations in `backend/tests/e2e/gold/*.json` (validated by
`_gold.GoldScenario`). Gold lives **outside** the ingested repo so it never perturbs the
per-stage integration tests.

### Scenario A — bug fix, introduced then repaired (`task.md`)

"Fix incorrect total when a discount exceeds the configured maximum, and add a boundary test."

The first canned implementation clamps at the **wrong** constant (`min(discount, 0.6)`), so the
generated boundary test (`calculate_total(100.0, 0.9) == 50.0`) **fails** in the fake sandbox.
The pipeline then investigates, the bounded repair loop supplies the correct constant
(`min(discount, 0.5)`), the repaired ops are **promoted onto the Implementation row in place**
(the Phase 24 wiring fix — see §4), `execute_retry` passes, and verification returns `VERIFIED`.
Terminal state: `COMPLETED`. Every one of the 18 workflow steps produces a persisted structured
output (asserted individually, and cross-checked against the 18-section
`report_builder.build_task_report`).

### Scenario B — feature request, file creation (`task_feature.md`)

"Add order-level tax: new `tax.py` with `apply_tax(subtotal, rate)`, wired into
`order_service.finalize_order`, with tests."

The plan's `files_to_modify` lists only the existing `order_service.py` (a plan may not name a
file absent from the snapshot); `tax.py` is created by a `create` edit-op, and the task's
`allowed_paths` includes `tax.py` so it is in scope. The generated `test_tax.py` passes first
time. Because a purely-additive feature cannot earn a mandatory `acceptance_tests_pass` PASS in
the Docker-less fake-sandbox run (the targeted-test heuristic does not bind a brand-new symbol),
verification is `PARTIAL` and reaches `COMPLETED` via a human `APPROVE` decision — an honest,
documented outcome, not a failure.

### Scenario C — unfixable, clean SAFE_STOP (`aegis-acceptance-unfixable/task.md`)

"Make `round_half_away()` round halves away from zero."

The canned implementation and repair proposals are deliberately ineffective, so the bounded
loop stalls on a repeated failure signature and returns `SAFE_STOP` with a populated `SafeStop`
payload (`recommended_human_action`). The task never reaches `COMPLETED` and verification never
returns `VERIFIED`; nothing crashes.

## 4. The Phase 24 wiring fix

Before Phase 24 a `REPAIRED` repair-loop result was persisted only as `RepairAttempt` rows —
`final_edit_ops` was consumed nowhere, so `execute_retry` and verification re-reconstructed the
*incomplete* implementation and an introduced-then-repaired run could never reach `VERIFIED`.

`app/services/repair.py::get_or_repair` now calls
`app/services/implementation.py::apply_repaired_ops(...)` on a `REPAIRED` outcome: it stacks the
repair ops onto the latest `Implementation` row **in place** (same id, so the test-case→impl and
execution→impl bindings stay valid) and rewrites that row's `Patch` + diff artifact. Covered by
`backend/tests/integration/test_repair_promotes_implementation.py`.

## 5. The 18 steps → code

| # | Step (Spec §39) | Stage / module | Report section |
|---|---|---|---|
| 1 | Ingest repository | `ingestion/ingest.py` | Repository |
| 2 | Understand repository | `analysis/analyze.py` | Understanding |
| 3 | Map issue → code | `services/mapping.py` | Code mapping |
| 4 | Identify relevant files | mapping candidates / plan `files_to_modify` | Code mapping |
| 5 | Analyze impact | `services/impact.py` | Impact |
| 6 | Create plan (+ validate) | `services/planning.py` | Plan |
| 7 | Implement fix | `services/implementation.py` | Implementation |
| 8 | Generate tests | `services/testing.py` | Tests |
| 9 | Execute tests | `services/execution.py` (fake / Docker) | (feeds Failures) |
| 10 | Detect introduced failure | orchestrator `_FAILING` gate | Failures |
| 11 | Investigate | `services/investigation.py` | Failures |
| 12 | Repair (bounded loop) | `services/repair.py` → `debugging/repair_loop.py` | Repairs |
| 13 | Run regression tests | `services/regression.py` | Regression results |
| 14 | Review patch | `services/review.py` | Review |
| 15 | Risk / confidence | `services/scoring.py` | Risk, Confidence |
| 16 | Verify implementation | `services/verification.py` | Verification |
| 17 | Generate final diff | `implementation/patcher.py` (persisted `Patch`) | Patch |
| 18 | (optional) create PR | `services/pr.py` (`LOCAL_ARTIFACT` without a token) | PR information |

## 6. Running

```
cd backend && pytest tests/e2e/test_full_pipeline.py -q          # 18-step E2E, scenarios A/B/C
cd backend && pytest tests/unit/test_acceptance_fixture_integrity.py -q
python scripts/build_acceptance_repo.py /tmp/acc                 # inspect the crafted history
```

The E2E runs with the mock provider + fake sandbox in CI (`pytest tests` already collects
`tests/e2e/`). `test_docker_variant_reaches_verified` re-runs scenario A through a real Docker
daemon and auto-skips when none is present.
