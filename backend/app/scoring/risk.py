"""Change Risk Score (CRS), 0-100, higher = riskier.
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 4.10.2 / docs/METRICS.md Section 2.2.

Pure weighted sum over already-normalized ``Signal``s -- no gates, no
multiplier. All constants come from ``model_registry``.
"""

from __future__ import annotations

from app.scoring._signal import Contribution, ScoreResult, Signal
from app.scoring.model_registry import (
    CRS_CLASSIFICATION,
    CRS_WEIGHTS,
    SCORING_MODEL_VERSION,
    UNAVAILABLE_PRIOR_RISK,
)


def _classify(value: int) -> str:
    if value <= CRS_CLASSIFICATION["LOW"]:
        return "LOW"
    if value <= CRS_CLASSIFICATION["MEDIUM"]:
        return "MEDIUM"
    if value <= CRS_CLASSIFICATION["HIGH"]:
        return "HIGH"
    return "CRITICAL"


def compute_crs(signals: list[Signal]) -> ScoreResult:
    by_name = {s.name: s for s in signals}

    contributions: list[Contribution] = []
    raw_sum = 0.0
    missing_weight = 0.0
    for name, weight in CRS_WEIGHTS.items():
        sig = by_name.get(name)
        if sig is None:  # defensive: a collector gap becomes a documented prior
            sig = Signal(
                name=name,
                raw=None,
                normalized=UNAVAILABLE_PRIOR_RISK,
                basis="INFERENCE",
                unavailable_reason="signal not collected",
            )
        contribution = weight * sig.normalized
        raw_sum += contribution
        if not sig.available:
            missing_weight += weight
        contributions.append(
            Contribution(
                name=name,
                raw=sig.raw,
                normalized=sig.normalized,
                weight=weight,
                contribution=contribution,
                basis=sig.basis,
                unavailable_reason=sig.unavailable_reason,
                evidence=list(sig.evidence),
            )
        )

    crs_raw = 100.0 * raw_sum
    value = round(crs_raw)

    return ScoreResult(
        value=value,
        classification=_classify(value),
        contributions=contributions,
        overall_confidence=round(1.0 - missing_weight, 2),
        model_version=SCORING_MODEL_VERSION,
        raw=round(crs_raw, 4),
    )
