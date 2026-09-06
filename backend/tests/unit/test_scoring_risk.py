"""CRS pure-function behaviour (docs/METRICS.md Section 2.2)."""

from __future__ import annotations

from app.scoring._signal import Signal
from app.scoring.risk import compute_crs
from app.scoring.model_registry import CRS_WEIGHTS


def _signals(overrides: dict[str, float] | None = None) -> list[Signal]:
    overrides = overrides or {}
    return [
        Signal(name, None, overrides.get(name, 0.0), "FACT")
        for name in CRS_WEIGHTS
    ]


def test_no_risk_signals_score_0_low():
    r = compute_crs(_signals())
    assert r.value == 0
    assert r.classification == "LOW"
    assert r.model_version == "scoring-model v1.0.0"


def test_all_max_signals_score_100_critical():
    r = compute_crs(_signals({n: 1.0 for n in CRS_WEIGHTS}))
    assert r.value == 100
    assert r.classification == "CRITICAL"


def test_contributions_sum_to_value():
    r = compute_crs(_signals({"files_changed": 1.0, "public_api_touched": 1.0}))
    assert round(sum(c.contribution for c in r.contributions) * 100) == r.value


def test_threshold_bands():
    def band(target: int) -> str:
        # public_api_touched has weight 0.15 -> tune it to hit `target`
        return compute_crs(
            _signals({"public_api_touched": target / 100 / CRS_WEIGHTS["public_api_touched"]})
        ).classification

    assert band(24) == "LOW"
    assert band(25) == "MEDIUM"
    assert band(49) == "MEDIUM"
    assert band(50) == "HIGH"
    assert band(74) == "HIGH"
    assert band(75) == "CRITICAL"


def test_bigger_diff_raises_the_band():
    small = compute_crs(_signals({"lines_changed": 0.1}))
    large = compute_crs(_signals({"lines_changed": 1.0}))
    assert large.value > small.value


def test_overall_confidence_drops_for_unavailable_signals():
    sigs = _signals()
    for s in sigs:
        if s.name in ("inverse_coverage", "historical_churn"):  # 0.13 + 0.08
            s.unavailable_reason = "no data"
    assert compute_crs(sigs).overall_confidence == round(1.0 - 0.21, 2)
