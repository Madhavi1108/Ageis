"""PCS pure-function behaviour (docs/METRICS.md Section 2.1)."""

from __future__ import annotations

import random

from app.scoring._signal import Signal
from app.scoring.confidence import compute_pcs
from app.scoring.model_registry import PCS_HARD_CAP, PCS_WEIGHTS


def _signals(overrides: dict[str, float] | None = None) -> list[Signal]:
    overrides = overrides or {}
    return [
        Signal(name, None, overrides.get(name, 1.0), "FACT")
        for name in PCS_WEIGHTS
    ]


def test_all_perfect_signals_score_100_high():
    r = compute_pcs(_signals())
    assert r.value == 100
    assert r.classification == "HIGH"
    assert r.model_version == "scoring-model v1.0.0"


def test_contributions_sum_to_raw_over_100():
    r = compute_pcs(_signals({"targeted_pass": 0.5, "review_clean": 0.2}))
    total = sum(c.contribution for c in r.contributions)
    assert round(total * 100, 6) == round(r.raw, 6)
    assert round(total * 100) == r.value  # security_gate == 1.0 here


def test_security_gate_scales_the_raw_score():
    base = compute_pcs(_signals()).value
    assert compute_pcs(_signals(), security_gate=0.6).value == round(base * 0.6)
    assert compute_pcs(_signals(), security_gate=0.0).value == 0


def test_classification_boundaries():
    # tune a single 0.10-weight signal to land exactly on each boundary
    def at(target: int) -> str:
        # start from all-1.0 (=100), subtract via the coverage signal (weight .10)
        drop = (100 - target) / 100 / PCS_WEIGHTS["coverage"]
        return compute_pcs(_signals({"coverage": 1.0 - drop})).classification

    assert at(86) == "HIGH"
    assert at(85) == "HIGH"
    assert at(84) == "MEDIUM"
    assert at(70) == "MEDIUM"
    assert at(69) == "LOW"
    assert at(50) == "LOW"
    assert at(49) == "VERY_LOW"


def test_hard_gate_caps_at_40_and_blocks():
    r = compute_pcs(_signals(), hard_gates=["failing_regression_test"])
    assert r.value <= PCS_HARD_CAP
    assert r.classification == "BLOCKED"
    assert r.hard_gate == ["failing_regression_test"]


def test_overall_confidence_drops_by_unavailable_weight():
    sigs = _signals()
    # mark coverage (0.10) + history_stable (0.04) unavailable
    for s in sigs:
        if s.name in ("coverage", "history_stable"):
            s.unavailable_reason = "no data"
    r = compute_pcs(sigs)
    assert r.overall_confidence == round(1.0 - 0.14, 2)


def test_property_adding_a_critical_never_raises_pcs():
    rng = random.Random(0)
    for _ in range(50):
        base_vals = {n: rng.random() for n in PCS_WEIGHTS}
        without = compute_pcs(
            [Signal(n, None, v, "FACT") for n, v in base_vals.items()]
        )
        # a CRITICAL finding forces review_clean toward 0 + a hard gate
        worse_vals = dict(base_vals, review_clean=0.0)
        with_crit = compute_pcs(
            [Signal(n, None, v, "FACT") for n, v in worse_vals.items()],
            security_gate=0.0,
            hard_gates=["unresolved_critical_review_finding"],
        )
        assert with_crit.value <= without.value
