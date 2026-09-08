"""``benchmarks.calibrate`` -- the scoring-model calibration check
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 33 step 5, docs/METRICS.md Section 5).

On any curated deterministic set the labeled sample is far below the re-fit
threshold, so the honest outcome is always RETAIN / INSUFFICIENT_DATA. These
tests pin that contract and the confusion-matrix arithmetic.
"""

from __future__ import annotations

from app.scoring.model_registry import SCORING_MODEL_VERSION
from benchmarks.calibrate import MIN_LABELED_FOR_REFIT, calibrate
from benchmarks.schema import BenchmarkResult, TaskRun


def _run(task_id, label, verdict):
    return TaskRun(
        task_id=task_id, dataset="unit", task_type="BUG",
        verification_label=label, verification_verdict=verdict,
    )


def test_calibrate_retains_v1_on_a_tiny_labeled_set():
    res = BenchmarkResult(dataset="unit", runs=[
        _run("a", "CORRECT", "VERIFIED"),
        _run("b", "INCORRECT", "NOT_VERIFIED"),
        _run("c", "CORRECT", "VERIFIED"),
    ])
    out = calibrate(res)
    assert out["action"] == "RETAIN"
    assert out["model_version"] == SCORING_MODEL_VERSION
    assert out["labeled_n"] == 3
    assert out["confusion"] == {"tp": 2, "tn": 1, "fp": 0, "fn": 0}
    assert out["false_complete_rate"] == 0.0
    assert all(c["verdict"] == "INSUFFICIENT_DATA" for c in out["per_constant"])
    assert SCORING_MODEL_VERSION in out["conclusion"]
    assert str(MIN_LABELED_FOR_REFIT) in out["conclusion"]


def test_calibrate_counts_a_false_complete():
    res = BenchmarkResult(dataset="unit", runs=[
        _run("fp", "INCORRECT", "VERIFIED"),
        _run("tn", "INCORRECT", "PARTIAL"),
    ])
    out = calibrate(res)
    assert out["confusion"] == {"tp": 0, "tn": 1, "fp": 1, "fn": 0}
    assert out["false_complete_rate"] == 0.5


def test_calibrate_ignores_unlabeled_and_errored_runs():
    res = BenchmarkResult(dataset="unit", runs=[
        _run("a", "CORRECT", "VERIFIED"),
        _run("b", None, "PARTIAL"),
        TaskRun(task_id="e", dataset="unit", task_type="BUG",
                verification_label="CORRECT", error="boom"),
    ])
    out = calibrate(res)
    assert out["labeled_n"] == 1
