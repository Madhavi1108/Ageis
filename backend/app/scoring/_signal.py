"""Internal value objects shared by the signal collectors and the three score
functions before they are projected into the ``app/schemas/scoring.py`` API
shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aegis.schemas.common import Evidence

Basis = str  # "FACT" | "INFERENCE"


@dataclass
class Signal:
    """One normalized model input.

    ``normalized`` is always in ``[0, 1]`` and is what the weighted sum uses.
    ``raw`` is the pre-normalization measurement (``None`` when the signal has
    no data source and ``normalized`` is a documented prior). ``basis`` is
    ``FACT`` for a directly measured value, ``INFERENCE`` for a heuristic or a
    prior.
    """

    name: str
    raw: float | None
    normalized: float
    basis: Basis
    unavailable_reason: str | None = None
    evidence: list[Evidence] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return self.unavailable_reason is None


@dataclass
class Contribution:
    """A signal's line in a score's explanation. ``contribution`` = weight *
    normalized; the contributions of a score sum to ``score_raw / 100``."""

    name: str
    raw: float | None
    normalized: float
    weight: float
    contribution: float
    basis: Basis
    unavailable_reason: str | None
    evidence: list[Evidence]


@dataclass
class ScoreResult:
    value: int
    classification: str
    contributions: list[Contribution]
    overall_confidence: float
    model_version: str
    # PCS-only extras (left at defaults for CRS/RHP)
    raw: float = 0.0
    security_gate: float = 1.0
    hard_gate: list[str] = field(default_factory=list)


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))
