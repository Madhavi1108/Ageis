"""Internal review-finding value object shared by the static / rule / AI layers
before aggregation into the ``ReviewFinding`` schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aegis.schemas.common import Confidence, Evidence


@dataclass
class RawFinding:
    source: str  # STATIC | RULE | AI
    category: str
    severity: str
    description: str
    recommendation: str = ""
    file: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    evidence: list[Evidence] = field(default_factory=list)
    confidence: Confidence = field(
        default_factory=lambda: Confidence(value=0.8, basis="FACT")
    )
