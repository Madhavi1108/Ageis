# AEGIS Cost & Latency Model

Traceability: `AEGIS_IMPLEMENTATION_PLAN.md` §4.13, Appendix F; metrics #13, #14. Phase 0
deliverable (plan addition). `ADR-0019` (model routing).

Status: Accepted — 2026-09-04. **All prices are `pricing-table v1.0.0` placeholders**; replaced
with real provider prices before the first live benchmark. Call counts are expected values, tuned
in Phase 25 with real traces.

---

## 1. Why cost is a first-class constraint

Autonomy is only useful if it is cheaper and faster than the human review it replaces. Every task
carries a **cost budget** (priced model spend) and a **wall-clock budget**, both enforced by the
Orchestrator (`EXECUTION_MODEL.md` §7). Exceeding a budget parks the task in `AWAITING_APPROVAL`
or `PARTIALLY_SUPPORTED` with partial artifacts — never a silent overrun.

---

## 2. Priced-model table (`pricing-table v1.0.0`)

| Tier | Input $/1M tok | Output $/1M tok |
|---|---|---|
| `cheap` | 0.30 | 1.20 |
| `frontier` | 3.00 | 15.00 |
| `embedding` | 0.02 | — |

Versioned; the CI cost-regression gate (`AEGIS_IMPLEMENTATION_PLAN.md` §5.7) uses this exact
table via `MockProvider` token accounting.

---

## 3. Per-stage call model (MVP pipeline, mid-size Python repo)

| Stage | Tier | Calls (exp.) | ~Input tok/call | ~Output tok/call |
|---|---|---|---|---|
| Task normalization | cheap | 1 | 1 000 | 300 |
| Issue->code mapping (rerank) | cheap | 3 | 3 000 | 500 |
| Impact summary | cheap | 1 | 3 000 | 600 |
| Engineering plan | frontier | 1 (+1 repair budgeted) | 8 000 | 2 000 |
| Implementation edit-ops | frontier | 1–2 | 10 000 | 3 000 |
| Test generation | frontier | 1–2 | 6 000 | 3 000 |
| Root-cause analysis (per repair iter) | frontier | 0–2 | 8 000 | 1 500 |
| Repair edit-ops (per repair iter) | frontier | 0–2 | 9 000 | 2 000 |
| Code review (AI pass) | frontier | 1 | 9 000 | 2 000 |
| Verification phrasing | cheap | 1 | 4 000 | 800 |
| Embedding index (per snapshot, amortized) | embedding | — | ~200 000 one-off | — |

---

## 4. Per-task cost envelope

Rough arithmetic with `pricing-table v1.0.0` (input+output priced):

| Scenario | Frontier calls | Cheap calls | Indicative model spend |
|---|---|---|---|
| **Low** (no repair) | ~4 | ~6 | ~$0.20–0.35 |
| **Expected** (1–2 repair iterations) | ~7 | ~6 | ~$0.40–0.75 |
| **High** (full repair budget) | capped by per-stage call budgets + repair iteration/wall-clock bounds | — | Orchestrator refuses to exceed; task parks instead |

These figures are indicative only and will move with real prices and real token traces. The
authoritative number after Phase 25 is metric #13 (`Cost per Verified Task`) in
`docs/BENCHMARK_RESULTS.md`.

Default budgets (config): `TASK_COST_BUDGET_USD = 2.00`, `TASK_WALLCLOCK_BUDGET_S = 2400`.

---

## 5. Levers when cost or latency regresses

1. **Model routing** — push a stage from `frontier` to `cheap` (config, per stage).
2. **Context windowing** — raise aggressiveness; the deterministic windower drops lower-priority
   context (history before related tests before neighbours before changed symbols) and records
   what it dropped.
3. **Repair cap** — lower `REPAIR_MAX_ITERATIONS`.
4. **Prompt caching** — cache the repository-context prefix shared across a task's stages.
5. **Marginal-improvement early-exit** — stop the repair loop when the reduction in failing tests
   per iteration falls below a threshold.
6. **Batch sandbox runs** — group targeted + related tests into one container start.

---

## 6. CI budget bands (`AEGIS_IMPLEMENTATION_PLAN.md` §5.7)

CI asserts, using `MockProvider` token accounting + `pricing-table v1.0.0`:

| Flow | Median cost band | P95 cost band | Median latency band | P95 latency band |
|---|---|---|---|---|
| Walking-skeleton E2E | <= $0.50 | <= $1.00 | <= 180 s | <= 360 s |
| Acceptance E2E (Phase 24) | <= $1.00 | <= $2.00 | <= 600 s | <= 1200 s |

Bands are provisional and re-based from measured Phase 25 data; a change that pushes a flow
outside its band fails the build until the band is re-justified with an ADR.

---

## 7. Open questions

| # | Question | Resolution |
|---|---|---|
| C1 | real provider prices | filled in before the first live benchmark; bump to `pricing-table v1.1.0` |
| C2 | embedding index refresh cost on large/active repos | measure in Phase 27; incremental re-index per snapshot delta |
| C3 | is $2.00/task the right default ceiling | revisit with metric #13 vs measured human-review cost |
