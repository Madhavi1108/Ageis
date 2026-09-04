# AEGIS Evaluation Harness

Traceability: `AEGIS_IMPLEMENTATION_PLAN.md` §5.6, §6, Phase 25; Specification §40, §41. Phase 0
deliverable (plan addition). Feeds `CAPABILITY_SPIKE.md` (Stage A) and Phase 25 benchmarking.

Status: Accepted — 2026-09-04. The harness is built for real in Phase 25; the throwaway spike
harness (`scripts/capability_spike/`) is a cut-down precursor.

---

## 1. Datasets

| Dataset | Purpose | Size | Tuning-visible? |
|---|---|---|---|
| **Capability subset** | Stage A spike (G0) + smoke in CI | ~30 tasks | yes (used to redesign retrieval/planning) |
| **Benchmark set** | Phase 25 metrics 1–16 | few hundred tasks | yes (calibration train split) |
| **Held-out "wild" set** | final measurement; overfitting check | ~50–100 real OSS issues | **no** — never used to tune retrieval, prompts, or weights |
| **Seeded-fault set** | metrics #5, #11 | crafted bugs with a test that passes iff fixed | yes |
| **Seeded-regression set** | metric #6 | changes that break an unrelated existing test | yes |
| **Seeded-defect set** | metric #9 | patches with a known planted defect | yes |
| **Labeled verification set** | metric #10 + false-complete rate | tasks with ground-truth correct/incorrect | yes (train split only) |

---

## 2. Task format (SWE-bench-Lite style)

```yaml
- id: <slug>
  repo: <url-or-fixture-path>
  base_commit: <sha>
  problem_statement: |
    <the issue text as a user would file it>
  gold_files: [<path>, ...]            # for metric #1 (localization)
  gold_patch: <path-to-diff>           # reference solution (not shown to AEGIS)
  test_cmd: "pytest -q <selection>"    # how to run the gold tests
  fail_to_pass: [<test id>, ...]       # tests that fail before, pass after a correct fix
  pass_to_pass: [<test id>, ...]       # tests that must stay green (regression guard)
  task_type: BUG | FEATURE | REFACTOR
  difficulty: EASY | MEDIUM | HARD
```

A task is **verified-fixed** iff, after AEGIS's patch, all `fail_to_pass` pass and all
`pass_to_pass` still pass, in the sandbox.

---

## 3. Metric computation (summary; full formulas in `METRICS.md` §1)

| Metric | Computed from |
|---|---|
| #1 localization | `F1` / `recall@k` of `IssueCodeMapping.candidates[].path` vs `gold_files` |
| #2 alignment | plan steps vs final diff + `unplanned_files` |
| #3 test validity | collect + determinism + assertion presence of generated tests |
| #4 pass rate | sandbox results |
| #5 repair success | seeded-fault tasks reaching green in the bounded loop |
| #6 regression detection | seeded-regression tasks where the regression suite flags the break |
| #7 acceptance | verified + scope-clean / generated |
| #8 scope compliance | scope-guard events |
| #9 defect detection | seeded-defect patches flagged by review |
| #10 verification accuracy + false-complete | verdicts vs labels |
| #11 mean repair iterations | repair ledger |
| #12 completion rate | task statuses |
| #13 cost per verified task | `MockProvider`/live token accounting x `pricing-table` / verified count |
| #14 latency P50/P95 | job timestamps |
| #15 competitive delta | AEGIS verified+scope-clean rate minus best reference agent on the **same** tasks |
| #16 replay fidelity | replay of a sampled subset vs original patch |

---

## 4. Reference agents (metric #15)

The harness can run the identical task set through open reference agents and record their
verified-fix outcomes with the same `fail_to_pass` / `pass_to_pass` criterion:

- **OpenHands** or **SWE-agent** (one general autonomous agent).
- **Aider** (a lighter, interactive-style agent run in batch mode).

Reference agents run in their own containers with the same resource limits. Their prompts/configs
are the project defaults, documented per run so the comparison is reproducible. AEGIS must beat the
best of them on **verified-change quality and false-complete rate**, not necessarily raw count.

---

## 5. Runner

`benchmarks/runner.py` (Phase 25):

```
for task in dataset:
    prepare sandbox from repo@base_commit
    run AEGIS headless -> collect all artifacts + token/cost accounting + timings
    evaluate fail_to_pass / pass_to_pass in the sandbox
    (optional) run each reference agent -> evaluate the same way
write results.json + results.xlsx + a Markdown summary
compute metrics 1-16 with confidence intervals
```

Deterministic with `MockProvider`; live runs behind `RUN_LIVE_AI=1`.

---

## 6. Calibration protocol (Phase 25)

1. Split the benchmark set + labeled verification set into train / held-out.
2. Fit `scoring-model` normalization bounds and weights on train against outcome labels with
   simple, explainable models (no un-explainable constant).
3. Fit `mapping-model` fusion weights on train against `gold_files`.
4. Evaluate everything on the held-out and the wild set; report measured metrics + CIs +
   limitations in `docs/BENCHMARK_RESULTS.md`.
5. Bump model versions with a changelog; update `METRICS.md` and the code registry together (the
   sync test enforces equality).

---

## 7. Decision gates fed by the harness

| Gate | Metric(s) | Threshold |
|---|---|---|
| G0 (Stage A) | localization `recall@10`; end-to-end verified-fix rate on the capability subset | `>= 0.75`; `>= 0.30` |
| G1 (M2) | localization `recall@10` on the **held-out** set; plan-validation reject rate on bad plans | `>= 0.70`; `>= 0.95` |
| G2 (M5) | false-complete rate on the labeled set | `<= 2%` |
| G3 (M8) | competitive delta (#15); cost per verified task (#13); replay fidelity (#16) | delta `>= 0`; within `COST_MODEL.md` envelope; `>= 0.9` |

---

## 8. Open questions

| # | Question | Resolution |
|---|---|---|
| EH1 | licence / redistribution of benchmark repos | use permissively licensed OSS + our own fixtures; record provenance per task |
| EH2 | flakiness of `pass_to_pass` in real repos | quarantine list + 2x retry; flaky tasks excluded from headline metrics with a note |
| EH3 | reference-agent version drift over time | pin versions per benchmark run; re-run baselines when AEGIS is re-measured |
