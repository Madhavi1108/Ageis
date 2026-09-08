"""Hand-computed fixtures for every one of the 16 objective-metric calculators
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 33 -- "each metric calculator against
hand-computed fixtures").

Each test builds a tiny ``BenchmarkResult`` from synthetic ``TaskRun`` rows and
asserts the calculator's value against a number worked out by hand in the
docstring, plus its ``basis`` (FACT vs UNAVAILABLE -- never a silent 0).
"""

from __future__ import annotations

import pytest

from benchmarks.metrics import (
    PRICING_TABLE,
    compute_all,
    metric_1,
    metric_2,
    metric_3,
    metric_4,
    metric_5,
    metric_6,
    metric_7,
    metric_8,
    metric_9,
    metric_10,
    metric_11,
    metric_12,
    metric_13,
    metric_14,
    metric_15,
    metric_16,
)
from benchmarks.schema import AICall, BenchmarkResult, TaskRun, TestEval


def _run(task_id: str = "t", **kw) -> TaskRun:
    base = dict(task_id=task_id, dataset="unit", task_type="BUG")
    base.update(kw)
    return TaskRun(**base)


def _result(*runs: TaskRun) -> BenchmarkResult:
    return BenchmarkResult(dataset="unit", runs=list(runs))


# --------------------------------------------------------------------------- #
# 1 -- Issue -> Code Mapping Accuracy
# --------------------------------------------------------------------------- #


def test_metric_1_f1_of_predicted_vs_gold():
    # task A: gold {a.py}; predicted [a.py, x.py] -> top-max(1,3)=3 preds,
    #   inter=1, prec=1/2, rec=1/1 -> F1 = 2*.5*1/1.5 = 0.6667
    # task B: gold {b.py, c.py}; predicted [b.py, c.py] -> inter 2,
    #   prec 1.0 rec 1.0 -> F1 = 1.0
    # mean F1 = (0.6667 + 1.0) / 2 = 0.8333
    res = _result(
        _run("a", gold_files=["a.py"], predicted_files=["a.py", "x.py"]),
        _run("b", gold_files=["b.py", "c.py"], predicted_files=["b.py", "c.py"]),
    )
    m = metric_1(res)
    assert m.basis == "FACT"
    assert m.n == 2
    assert m.value == pytest.approx(0.8333, abs=1e-4)


def test_metric_1_unavailable_without_gold():
    m = metric_1(_result(_run("a", predicted_files=["a.py"])))
    assert m.value is None
    assert m.basis == "UNAVAILABLE"


# --------------------------------------------------------------------------- #
# 2 -- Plan -> Implementation Alignment
# --------------------------------------------------------------------------- #


def test_metric_2_alignment_penalises_unplanned_files():
    # steps 2/2 done, 1 unplanned of 2 changed -> 1.0 * (1 - 1/2) = 0.5
    # steps 1/1 done, 0 unplanned of 1 changed  -> 1.0
    # ratio metric: sum(num)/sum(den) = (0.5 + 1.0) / (1 + 1) = 0.75
    res = _result(
        _run(
            "a",
            plan_steps_total=2,
            plan_steps_implemented=2,
            changed_files=["a.py", "b.py"],
            unplanned_files=["b.py"],
        ),
        _run("b", plan_steps_total=1, plan_steps_implemented=1, changed_files=["c.py"]),
    )
    m = metric_2(res)
    assert m.basis == "FACT"
    assert m.value == pytest.approx(0.75, abs=1e-4)


def test_metric_2_unavailable_without_plan():
    assert metric_2(_result(_run("a"))).basis == "UNAVAILABLE"


# --------------------------------------------------------------------------- #
# 3 -- Test Generation Validity
# --------------------------------------------------------------------------- #


def test_metric_3_valid_over_generated():
    # (3 + 1) valid / (4 + 2) generated = 4/6 = 0.6667
    res = _result(
        _run("a", tests_generated=4, tests_valid=3),
        _run("b", tests_generated=2, tests_valid=1),
    )
    m = metric_3(res)
    assert m.value == pytest.approx(0.6667, abs=1e-4)
    assert m.basis == "FACT"


def test_metric_3_unavailable_without_tests():
    assert metric_3(_result(_run("a"))).basis == "UNAVAILABLE"


# --------------------------------------------------------------------------- #
# 4 -- Test Pass Rate
# --------------------------------------------------------------------------- #


def test_metric_4_pass_rate_over_real_executions_only():
    # real run: 2 PASS of 3; degraded run ignored entirely -> 2/3
    res = _result(
        _run("a", real_execution=True, test_results=["PASS", "PASS", "FAIL"]),
        _run("b", real_execution=False, test_results=["PASS"]),
    )
    m = metric_4(res)
    assert m.value == pytest.approx(0.6667, abs=1e-4)
    assert m.n == 1


def test_metric_4_unavailable_without_real_execution():
    assert metric_4(_result(_run("a", real_execution=False))).basis == "UNAVAILABLE"


# --------------------------------------------------------------------------- #
# 5 -- Autonomous Repair Success Rate
# --------------------------------------------------------------------------- #


def test_metric_5_repaired_over_entered():
    res = _result(
        _run("a", entered_repair=True, repair_outcome="REPAIRED"),
        _run("b", entered_repair=True, repair_outcome="SAFE_STOP"),
        _run("c", entered_repair=False),
    )
    m = metric_5(res)
    assert m.value == pytest.approx(0.5)
    assert m.n == 2  # 'c' never entered repair


def test_metric_5_unavailable_when_nobody_repairs():
    assert metric_5(_result(_run("a"))).basis == "UNAVAILABLE"


# --------------------------------------------------------------------------- #
# 6 -- Regression Detection Rate
# --------------------------------------------------------------------------- #


def test_metric_6_caught_over_seeded():
    res = _result(
        _run("a", is_seeded_regression=True, regression_flagged=True),
        _run("b", is_seeded_regression=True, regression_flagged=False),
        _run("c", is_seeded_regression=False),
    )
    m = metric_6(res)
    assert m.value == pytest.approx(0.5)
    assert m.n == 2


def test_metric_6_unavailable_without_seeded_regressions():
    assert metric_6(_result(_run("a"))).basis == "UNAVAILABLE"


# --------------------------------------------------------------------------- #
# 7 -- Patch Acceptance Rate
# --------------------------------------------------------------------------- #


def test_metric_7_verified_and_scope_clean_over_generated():
    # a: verified + clean -> 1 ; b: verified + violation -> 0 ; c: no patch -> skip
    res = _result(
        _run("a", patch_generated=True, verification_verdict="VERIFIED"),
        _run("b", patch_generated=True, verification_verdict="VERIFIED", scope_violation=True),
        _run("c", patch_generated=False),
    )
    m = metric_7(res)
    assert m.value == pytest.approx(0.5)
    assert m.n == 2


# --------------------------------------------------------------------------- #
# 8 -- Scope Compliance
# --------------------------------------------------------------------------- #


def test_metric_8_one_minus_unjustified_violation_rate():
    # 1 unjustified violation of 4 tasks -> 1 - 1/4 = 0.75
    res = _result(
        _run("a"),
        _run("b"),
        _run("c"),
        _run("d", scope_violation=True),
    )
    m = metric_8(res)
    assert m.value == pytest.approx(0.75)
    assert m.n == 4


def test_metric_8_justified_violation_does_not_count():
    res = _result(_run("a", scope_violation=True, scope_violation_justified=True))
    assert metric_8(res).value == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# 9 -- Review Defect Detection
# --------------------------------------------------------------------------- #


def test_metric_9_flagged_over_seeded_defects():
    res = _result(
        _run("a", seeded_defect_kind="eval_exec", review_flagged_defect=True),
        _run("b", seeded_defect_kind="bare_except", review_flagged_defect=False),
        _run("c"),
    )
    m = metric_9(res)
    assert m.value == pytest.approx(0.5)
    assert m.n == 2


# --------------------------------------------------------------------------- #
# 10 -- Verification Accuracy + false-complete rate
# --------------------------------------------------------------------------- #


def test_metric_10_confusion_matrix_and_false_complete():
    # CORRECT + VERIFIED   -> TP
    # CORRECT + not         -> FN
    # INCORRECT + VERIFIED -> FP  (a false-complete)
    # INCORRECT + not       -> TN
    res = _result(
        _run("tp", verification_label="CORRECT", verification_verdict="VERIFIED"),
        _run("fn", verification_label="CORRECT", verification_verdict="NOT_VERIFIED"),
        _run("fp", verification_label="INCORRECT", verification_verdict="VERIFIED"),
        _run("tn", verification_label="INCORRECT", verification_verdict="PARTIAL"),
    )
    m = metric_10(res)
    assert m.value == pytest.approx(0.5)  # (TP + TN) / 4
    assert "false-complete rate = 0.5" in m.note  # FP / (FP + TN) = 1/2
    assert "TP=1 TN=1 FP=1 FN=1" in m.note


def test_metric_10_surfaces_the_pipeline_autonomous_verdicts():
    res = _result(
        _run("a", verification_label="CORRECT", verification_verdict="VERIFIED",
             pipeline_verdict="PARTIAL"),
    )
    assert "autonomous verdicts" in metric_10(res).note
    assert "'PARTIAL'" in metric_10(res).note


def test_metric_10_unavailable_without_labels():
    assert metric_10(_result(_run("a"))).basis == "UNAVAILABLE"


# --------------------------------------------------------------------------- #
# 11 -- Mean Repair Iterations
# --------------------------------------------------------------------------- #


def test_metric_11_mean_over_repairing_tasks():
    res = _result(
        _run("a", entered_repair=True, repair_iterations=1),
        _run("b", entered_repair=True, repair_iterations=3),
        _run("c", entered_repair=False, repair_iterations=0),
    )
    assert metric_11(res).value == pytest.approx(2.0)


# --------------------------------------------------------------------------- #
# 12 -- Task Completion Rate (ground-truth gated)
# --------------------------------------------------------------------------- #


def test_metric_12_needs_completed_and_ground_truth_green():
    green = TestEval(
        fail_to_pass={"t::a": True}, pass_to_pass={"t::b": True}
    )
    broke = TestEval(
        fail_to_pass={"t::a": True}, pass_to_pass={"t::b": False}
    )
    res = _result(
        _run("a", terminal_state="COMPLETED", test_eval=green),
        _run("b", terminal_state="COMPLETED", test_eval=broke),   # regressed -> not counted
        _run("c", terminal_state="AWAITING_APPROVAL", test_eval=green),  # not completed
    )
    m = metric_12(res)
    assert m.value == pytest.approx(1 / 3, abs=1e-4)
    assert m.n == 3


# --------------------------------------------------------------------------- #
# 13 -- Cost per Verified Task (USD, simulated)
# --------------------------------------------------------------------------- #


def test_metric_13_prices_tokens_against_the_table():
    # one frontier call: 1_000_000 in, 1_000_000 out
    #   -> 1 * 3.00 + 1 * 15.00 = 18.00 USD, over 1 verified task
    call = AICall(
        template="planning", tier="frontier",
        input_tokens=1_000_000, output_tokens=1_000_000,
    )
    res = _result(_run("a", verification_verdict="VERIFIED", ai_calls=[call]))
    m = metric_13(res)
    expected = PRICING_TABLE["frontier"]["input"] + PRICING_TABLE["frontier"]["output"]
    assert m.value == pytest.approx(expected)
    assert "SIMULATED" in m.note


def test_metric_13_unavailable_without_a_verified_task():
    call = AICall(template="x", tier="frontier", input_tokens=10, output_tokens=10)
    m = metric_13(_result(_run("a", verification_verdict="NOT_VERIFIED", ai_calls=[call])))
    assert m.basis == "UNAVAILABLE"
    assert "simulated spend so far" in m.note


# --------------------------------------------------------------------------- #
# 14 -- Task Latency P50 / P95
# --------------------------------------------------------------------------- #


def test_metric_14_reports_p50_seconds_with_p95_in_note():
    res = _result(*[_run(f"t{i}", wall_clock_ms=(i + 1) * 1000) for i in range(10)])
    m = metric_14(res)
    assert m.basis == "FACT"
    assert m.n == 10
    assert m.value == pytest.approx(5.5, abs=0.5)  # median of 1..10s
    assert "P95=" in m.note


def test_metric_14_unavailable_without_timings():
    assert metric_14(_result(_run("a", wall_clock_ms=0))).basis == "UNAVAILABLE"


# --------------------------------------------------------------------------- #
# 15 -- Competitive Resolution-Rate Delta
# --------------------------------------------------------------------------- #


def test_metric_15_delta_against_best_reference_agent():
    # aegis: 1 of 2 verified+clean = 0.5 ; ref 'aider' solved 0 of 2 = 0.0
    res = _result(
        _run("a", verification_verdict="VERIFIED", reference_outcomes={"aider": False}),
        _run("b", verification_verdict="NOT_VERIFIED", reference_outcomes={"aider": False}),
    )
    m = metric_15(res)
    assert m.value == pytest.approx(0.5)


def test_metric_15_unavailable_without_reference_agents():
    assert metric_15(_result(_run("a"))).basis == "UNAVAILABLE"


# --------------------------------------------------------------------------- #
# 16 -- Deterministic Replay Fidelity
# --------------------------------------------------------------------------- #


def test_metric_16_mean_replay_fidelity():
    res = _result(
        _run("a", replay_fidelity=1.0),
        _run("b", replay_fidelity=0.0),
    )
    assert metric_16(res).value == pytest.approx(0.5)


def test_metric_16_unavailable_without_replay():
    assert metric_16(_result(_run("a"))).basis == "UNAVAILABLE"


# --------------------------------------------------------------------------- #
# compute_all -- the full set, in order, no gaps
# --------------------------------------------------------------------------- #


def test_compute_all_returns_16_metrics_numbered_1_to_16():
    res = _result(_run("a", gold_files=["a.py"], predicted_files=["a.py"]))
    metrics = compute_all(res)
    assert [m.number for m in metrics] == list(range(1, 17))
    # every metric is either a real measurement or an explicit UNAVAILABLE
    for m in metrics:
        assert m.basis in {"FACT", "UNAVAILABLE"}
        if m.basis == "UNAVAILABLE":
            assert m.value is None and m.note  # never a silent 0
