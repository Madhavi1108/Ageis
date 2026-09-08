"""The 16 objective-metric calculators (docs/METRICS.md Section 1).

Every calculator is a pure function of a ``BenchmarkResult`` and returns a
``MetricValue`` carrying the formula it applied, the number of data points, and
-- where n >= 2 and the sample varies -- a bootstrap 95% CI. A metric with no
data source in the current run is ``basis="UNAVAILABLE"`` with an explicit
reason (never a silent 0).
"""

from __future__ import annotations

import random
import statistics
from typing import Callable

from pydantic import BaseModel

from benchmarks.schema import BenchmarkResult, TaskRun

# pricing-table v1.0.0 -- mirrors docs/METRICS.md Section 3 (placeholder prices,
# USD per 1M tokens). Metric #13 is a *simulated* cost until real provider
# prices and live token accounting land.
PRICING_TABLE_VERSION = "pricing-table v1.0.0"
PRICING_TABLE = {
    "cheap": {"input": 0.30, "output": 1.20},
    "frontier": {"input": 3.00, "output": 15.00},
    "embedding": {"input": 0.02, "output": 0.0},
}

_RECALL_K = 10


class MetricValue(BaseModel):
    number: int
    name: str
    formula: str
    value: float | None
    basis: str  # FACT | UNAVAILABLE
    n: int
    ci95: tuple[float, float] | None = None
    note: str = ""


def bootstrap_ci95(values: list[float], *, n_boot: int = 2000, seed: int = 12345) -> tuple[float, float] | None:
    vals = [float(v) for v in values]
    if len(vals) < 2 or min(vals) == max(vals):
        return None
    rng = random.Random(seed)
    means = []
    n = len(vals)
    for _ in range(n_boot):
        sample = [vals[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(0.025 * n_boot)]
    hi = means[int(0.975 * n_boot)]
    return (round(lo, 4), round(hi, 4))


def _ok(result: BenchmarkResult) -> list[TaskRun]:
    return [r for r in result.runs if r.error is None]


def _ratio_metric(
    number: int,
    name: str,
    formula: str,
    per_task: Callable[[TaskRun], tuple[float, float] | None],
    runs: list[TaskRun],
    *,
    unavailable_reason: str,
    note: str = "",
) -> MetricValue:
    """``per_task`` returns ``(numerator, denominator)`` or ``None`` to skip."""
    pairs = [p for p in (per_task(r) for r in runs) if p is not None]
    num = sum(p[0] for p in pairs)
    den = sum(p[1] for p in pairs)
    if den == 0:
        return MetricValue(
            number=number, name=name, formula=formula, value=None,
            basis="UNAVAILABLE", n=0, note=unavailable_reason,
        )
    per_task_vals = [p[0] / p[1] for p in pairs if p[1]]
    return MetricValue(
        number=number, name=name, formula=formula, value=round(num / den, 4),
        basis="FACT", n=len(pairs), ci95=bootstrap_ci95(per_task_vals), note=note,
    )


# --------------------------------------------------------------------------- #
# 1 -- Issue -> Code Mapping Accuracy
# --------------------------------------------------------------------------- #


def metric_1(result: BenchmarkResult) -> MetricValue:
    """F1 of predicted files vs gold files (recall@10 in the note).

    Inputs: ``IssueCodeMapping.candidates[].path`` vs each task's ``gold_files``.
    Higher = better localization. Limitation: sensitive to gold-set granularity;
    F1 uses the top-|gold| candidates, recall@10 the top 10.
    """
    runs = [r for r in _ok(result) if r.gold_files]
    if not runs:
        return MetricValue(number=1, name="Issue->Code Mapping Accuracy",
                           formula="F1(predicted_files, gold_files)", value=None,
                           basis="UNAVAILABLE", n=0, note="no tasks carry gold_files")
    f1s, recalls = [], []
    for r in runs:
        gold = set(r.gold_files)
        topf = set(r.predicted_files[: max(len(gold), 3)])
        inter = len(topf & gold)
        prec = inter / len(topf) if topf else 0.0
        rec = inter / len(gold)
        f1s.append(2 * prec * rec / (prec + rec) if (prec + rec) else 0.0)
        rk = set(r.predicted_files[:_RECALL_K])
        recalls.append(len(rk & gold) / len(gold))
    mean_f1 = round(sum(f1s) / len(f1s), 4)
    return MetricValue(
        number=1, name="Issue->Code Mapping Accuracy",
        formula="mean F1(top-|gold| predicted, gold_files)",
        value=mean_f1, basis="FACT", n=len(runs), ci95=bootstrap_ci95(f1s),
        note=f"recall@{_RECALL_K} = {round(sum(recalls) / len(recalls), 4)}",
    )


def metric_2(result: BenchmarkResult) -> MetricValue:
    """Plan->Implementation Alignment: `(steps_impl / steps_total) * (1 - unplanned / max(1, changed))`.

    1.0 = every plan step implemented and nothing outside the plan changed.
    """
    def per(r: TaskRun):
        if r.plan_steps_total <= 0:
            return None
        done = (r.plan_steps_implemented / r.plan_steps_total)
        changed = max(1, len(r.changed_files))
        align = done * (1 - len(r.unplanned_files) / changed)
        return (align, 1.0)

    return _ratio_metric(
        2, "Plan->Implementation Alignment",
        "(steps_impl/steps_total) * (1 - unplanned/max(1,changed))",
        per, _ok(result),
        unavailable_reason="no task produced a plan-alignment record",
    )


def metric_3(result: BenchmarkResult) -> MetricValue:
    """Test Generation Validity: `tests_valid / tests_generated`."""
    return _ratio_metric(
        3, "Test Generation Validity", "tests_valid / tests_generated",
        lambda r: (r.tests_valid, r.tests_generated) if r.tests_generated else None,
        _ok(result), unavailable_reason="no tests were generated",
    )


def metric_4(result: BenchmarkResult) -> MetricValue:
    """Test Pass Rate: `tests_passed / tests_executed` over real (non-degraded) runs."""
    def per(r: TaskRun):
        if not r.real_execution or not r.test_results:
            return None
        return (sum(1 for o in r.test_results if o == "PASS"), len(r.test_results))

    return _ratio_metric(
        4, "Test Pass Rate", "tests_passed / tests_executed", per, _ok(result),
        unavailable_reason="no real (non PARTIALLY_SUPPORTED) executions -- needs the sandbox",
    )


def metric_5(result: BenchmarkResult) -> MetricValue:
    """Autonomous Repair Success Rate: `repaired_to_green / tasks_entering_repair`."""
    return _ratio_metric(
        5, "Autonomous Repair Success Rate", "repaired_to_green / tasks_entering_repair",
        lambda r: (1.0 if r.repair_outcome == "REPAIRED" else 0.0, 1.0) if r.entered_repair else None,
        _ok(result), unavailable_reason="no task entered the repair loop -- needs a seeded-fault set",
    )


def metric_6(result: BenchmarkResult) -> MetricValue:
    """Regression Detection Rate: `injected_regressions_caught / injected_regressions_total`.

    Limitation: the Docker-less pipeline does not execute regression tests
    in-stage, so 'caught' means the broken ``pass_to_pass`` test is in the
    regression plan's selected set (or, with no selection detail, that the
    benchmark's own pass_to_pass re-run flagged the break).
    """
    return _ratio_metric(
        6, "Regression Detection Rate", "injected_regressions_caught / injected_regressions_total",
        lambda r: (1.0 if r.regression_flagged else 0.0, 1.0) if r.is_seeded_regression else None,
        _ok(result), unavailable_reason="needs a seeded-regression set",
    )


def metric_7(result: BenchmarkResult) -> MetricValue:
    """Patch Acceptance Rate: `patches_verified_and_scope_clean / patches_generated`."""
    return _ratio_metric(
        7, "Patch Acceptance Rate", "verified_and_scope_clean / patches_generated",
        lambda r: (
            1.0 if (r.verification_verdict == "VERIFIED" and not r.scope_violation) else 0.0,
            1.0,
        ) if r.patch_generated else None,
        _ok(result), unavailable_reason="no patch was generated",
    )


def metric_8(result: BenchmarkResult) -> MetricValue:
    """Scope Compliance: `1 - tasks_with_unjustified_scope_violation / tasks_total`.

    Limitation: there is no 'override with reason' data model, so any scope
    violation counts as unjustified (METRICS.md #8).
    """
    runs = _ok(result)
    if not runs:
        return MetricValue(number=8, name="Scope Compliance",
                           formula="1 - unjustified_scope_violations / tasks",
                           value=None, basis="UNAVAILABLE", n=0, note="no tasks ran")
    bad = sum(1 for r in runs if r.scope_violation and not r.scope_violation_justified)
    per = [0.0 if (r.scope_violation and not r.scope_violation_justified) else 1.0 for r in runs]
    return MetricValue(
        number=8, name="Scope Compliance", formula="1 - unjustified_scope_violations / tasks",
        value=round(1 - bad / len(runs), 4), basis="FACT", n=len(runs), ci95=bootstrap_ci95(per),
    )


def metric_9(result: BenchmarkResult) -> MetricValue:
    """Review Defect Detection: `seeded_defects_flagged / seeded_defects_total`."""
    return _ratio_metric(
        9, "Review Defect Detection", "seeded_defects_flagged / seeded_defects_total",
        lambda r: (1.0 if r.review_flagged_defect else 0.0, 1.0) if r.seeded_defect_kind else None,
        _ok(result), unavailable_reason="needs seeded-defect patches",
    )


def metric_10(result: BenchmarkResult) -> MetricValue:
    """Verification Accuracy: `(TP + TN) / total`; false-complete `= FP / (FP + TN)` in the note.

    Scored against AEGIS's final verdict (``verification_verdict``). In this
    Docker-less environment the pipeline never reaches ``VERIFIED`` autonomously
    (targeted tests are not executed in-stage -- ``pipeline_verdict`` is
    reported alongside as always ``PARTIAL``); the benchmark's own ground-truth
    ``fail_to_pass``/``pass_to_pass`` gate is what promotes a task to
    ``VERIFIED``. That gate makes a false-complete structurally impossible here,
    which is the property this metric is meant to demonstrate -- but a real
    false-complete rate needs the live sandbox + a larger labeled set.
    """
    runs = [r for r in _ok(result) if r.verification_label]
    if not runs:
        return MetricValue(number=10, name="Verification Accuracy",
                           formula="(TP+TN)/total; false-complete=FP/(FP+TN)",
                           value=None, basis="UNAVAILABLE", n=0,
                           note="needs a labeled verification set")
    tp = tn = fp = fn = 0
    for r in runs:
        verified = r.verification_verdict == "VERIFIED"
        if r.verification_label == "CORRECT":
            tp += verified
            fn += not verified
        else:
            fp += verified
            tn += not verified
    total = tp + tn + fp + fn
    fc_den = fp + tn
    fc = fp / fc_den if fc_den else 0.0
    per = ([1.0] * (tp + tn)) + ([0.0] * (fp + fn))
    autonomous = sorted({r.pipeline_verdict or "?" for r in runs})
    return MetricValue(
        number=10, name="Verification Accuracy",
        formula="(TP+TN)/total; false-complete=FP/(FP+TN)",
        value=round((tp + tn) / total, 4), basis="FACT", n=len(runs),
        ci95=bootstrap_ci95(per),
        note=(
            f"false-complete rate = {round(fc, 4)} (ceiling 0.02); "
            f"TP={tp} TN={tn} FP={fp} FN={fn}; "
            f"pipeline autonomous verdicts (pre ground-truth gate): {autonomous}"
        ),
    )


def metric_11(result: BenchmarkResult) -> MetricValue:
    """Mean Repair Iterations: `sum(iterations) / tasks_entering_repair`."""
    runs = [r for r in _ok(result) if r.entered_repair]
    if not runs:
        return MetricValue(number=11, name="Mean Repair Iterations",
                           formula="sum(iterations) / tasks_entering_repair",
                           value=None, basis="UNAVAILABLE", n=0,
                           note="no task entered the repair loop")
    per = [float(r.repair_iterations) for r in runs]
    return MetricValue(
        number=11, name="Mean Repair Iterations",
        formula="sum(iterations) / tasks_entering_repair",
        value=round(sum(per) / len(per), 4), basis="FACT", n=len(runs),
        ci95=bootstrap_ci95(per),
    )


def metric_12(result: BenchmarkResult) -> MetricValue:
    """Task Completion Rate: `tasks_completed_verified / tasks_submitted`.

    "Completed & verified" = the task reached ``COMPLETED`` *and* the
    reconstructed final workspace actually passes every ``fail_to_pass`` while
    keeping every ``pass_to_pass`` green (ground truth, not the verdict alone).
    """
    runs = _ok(result)
    if not runs:
        return MetricValue(number=12, name="Task Completion Rate",
                           formula="completed_verified / submitted", value=None,
                           basis="UNAVAILABLE", n=0, note="no tasks ran")
    per = [
        1.0 if (r.terminal_state == "COMPLETED" and r.test_eval.verified_fixed) else 0.0
        for r in runs
    ]
    return MetricValue(
        number=12, name="Task Completion Rate", formula="completed_verified / submitted",
        value=round(sum(per) / len(per), 4), basis="FACT", n=len(runs),
        ci95=bootstrap_ci95(per),
    )


def _priced(run: TaskRun) -> float:
    usd = 0.0
    for c in run.ai_calls:
        tier = PRICING_TABLE.get(c.tier, PRICING_TABLE["frontier"])
        usd += c.input_tokens / 1_000_000 * tier["input"]
        usd += c.output_tokens / 1_000_000 * tier["output"]
    return usd


def metric_13(result: BenchmarkResult) -> MetricValue:
    """Cost per Verified Task (USD): `total_priced_model_spend / tasks_verified`.

    Simulated: ``pricing-table v1.0.0`` placeholder prices x approximate
    MockProvider token counts. Not a real cost until live token accounting +
    real provider prices land.
    """
    runs = _ok(result)
    verified = [r for r in runs if r.verification_verdict == "VERIFIED"]
    total_spend = sum(_priced(r) for r in runs)
    if not verified:
        return MetricValue(number=13, name="Cost per Verified Task (USD)",
                           formula="total_priced_model_spend / tasks_verified",
                           value=None, basis="UNAVAILABLE", n=0,
                           note=f"no verified task; simulated spend so far ${round(total_spend, 6)}")
    return MetricValue(
        number=13, name="Cost per Verified Task (USD)",
        formula="total_priced_model_spend / tasks_verified",
        value=round(total_spend / len(verified), 6), basis="FACT", n=len(verified),
        note=f"SIMULATED -- {PRICING_TABLE_VERSION} placeholder prices x approx MockProvider tokens",
    )


def metric_14(result: BenchmarkResult) -> MetricValue:
    """Task Latency P50 / P95 (seconds): percentiles of wall-clock run->terminal."""
    runs = _ok(result)
    secs = sorted(r.wall_clock_ms / 1000 for r in runs if r.wall_clock_ms)
    if not secs:
        return MetricValue(number=14, name="Task Latency P50 / P95",
                           formula="percentiles(wall_clock)", value=None,
                           basis="UNAVAILABLE", n=0, note="no timed runs")
    if len(secs) == 1:
        p50 = p95 = secs[0]
    else:
        qs = statistics.quantiles(secs, n=100, method="inclusive")
        p50, p95 = qs[49], qs[94]
    return MetricValue(
        number=14, name="Task Latency P50 / P95", formula="percentiles(wall_clock run->terminal)",
        value=round(p50, 3), basis="FACT", n=len(secs),
        note=f"P50={round(p50, 3)}s  P95={round(p95, 3)}s  (fake sandbox; not representative of Docker)",
    )


def metric_15(result: BenchmarkResult) -> MetricValue:
    """Competitive Resolution-Rate Delta: `aegis_rate - best_reference_agent_rate`."""
    runs = _ok(result)
    agents = sorted({a for r in runs for a in r.reference_outcomes})
    if not agents:
        return MetricValue(number=15, name="Competitive Resolution-Rate Delta",
                           formula="aegis_verified_scope_clean_rate - best_reference_rate",
                           value=None, basis="UNAVAILABLE", n=0,
                           note="no reference agents configured")
    aegis = sum(
        1 for r in runs if r.verification_verdict == "VERIFIED" and not r.scope_violation
    ) / len(runs)
    best = max(
        sum(1 for r in runs if r.reference_outcomes.get(a)) / len(runs) for a in agents
    )
    return MetricValue(
        number=15, name="Competitive Resolution-Rate Delta",
        formula="aegis_verified_scope_clean_rate - best_reference_rate",
        value=round(aegis - best, 4), basis="FACT", n=len(runs),
        note=f"agents={agents}; aegis={round(aegis, 4)} best_ref={round(best, 4)}",
    )


def metric_16(result: BenchmarkResult) -> MetricValue:
    """Deterministic Replay Fidelity: mean verification ``replay_fidelity``."""
    runs = [r for r in _ok(result) if r.replay_fidelity is not None]
    if not runs:
        return MetricValue(number=16, name="Deterministic Replay Fidelity",
                           formula="tasks_replaying_to_identical_patch / tasks_sampled",
                           value=None, basis="UNAVAILABLE", n=0,
                           note="no verification recorded a replay_fidelity")
    per = [float(r.replay_fidelity) for r in runs]  # type: ignore[arg-type]
    return MetricValue(
        number=16, name="Deterministic Replay Fidelity",
        formula="mean(verification.replay_fidelity)",
        value=round(sum(per) / len(per), 4), basis="FACT", n=len(runs),
        ci95=bootstrap_ci95(per),
        note="replay_fidelity is check_reapplies (1.0/0.0), not a full replay manifest (Phase 20 open item)",
    )


_CALCULATORS = [
    metric_1, metric_2, metric_3, metric_4, metric_5, metric_6, metric_7, metric_8,
    metric_9, metric_10, metric_11, metric_12, metric_13, metric_14, metric_15, metric_16,
]


def compute_all(result: BenchmarkResult) -> list[MetricValue]:
    return [calc(result) for calc in _CALCULATORS]
