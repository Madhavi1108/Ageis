"""Patch Confidence Score (PCS), 0-100, higher = safer to accept.
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 4.10.1 / docs/METRICS.md Section 2.1.

Pure function over a list of already-normalized ``Signal``s plus the two
things that are not weighted signals -- the ``security_gate`` multiplier and
the list of fired hard gates. All constants come from ``model_registry``.
"""

from __future__ import annotations

from app.scoring._signal import Contribution, ScoreResult, Signal
from app.scoring.model_registry import (
    PCS_CLASSIFICATION,
    PCS_HARD_CAP,
    PCS_WEIGHTS,
    SCORING_MODEL_VERSION,
    UNAVAILABLE_PRIOR_GOOD,
)


def _classify(value: int) -> str:
    if value >= PCS_CLASSIFICATION["HIGH"]:
        return "HIGH"
    if value >= PCS_CLASSIFICATION["MEDIUM"]:
        return "MEDIUM"
    if value >= PCS_CLASSIFICATION["LOW"]:
        return "LOW"
    return "VERY_LOW"


def compute_pcs(
    signals: list[Signal],
    *,
    security_gate: float = 1.0,
    hard_gates: list[str] | None = None,
) -> ScoreResult:
    by_name = {s.name: s for s in signals}
    hard_gates = list(hard_gates or [])

    contributions: list[Contribution] = []
    raw_sum = 0.0
    missing_weight = 0.0
    for name, weight in PCS_WEIGHTS.items():
        sig = by_name.get(name)
        if sig is None:  # defensive: a collector gap becomes a documented prior
            sig = Signal(
                name=name,
                raw=None,
                normalized=UNAVAILABLE_PRIOR_GOOD,
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

    pcs_raw = 100.0 * raw_sum
    value = round(pcs_raw * security_gate)

    if hard_gates:
        value = min(value, PCS_HARD_CAP)
        classification = "BLOCKED"
    else:
        classification = _classify(value)

    return ScoreResult(
        value=value,
        classification=classification,
        contributions=contributions,
        overall_confidence=round(1.0 - missing_weight, 2),
        model_version=SCORING_MODEL_VERSION,
        raw=round(pcs_raw, 4),
        security_gate=security_gate,
        hard_gate=hard_gates,
    )
