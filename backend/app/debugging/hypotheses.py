"""Hypothesis ranking for the repair loop (docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 22, step 3). Pure and deterministic.

Order: label priority (FACT > INFERENCE > HYPOTHESIS), then the model's own
``rank`` ascending, then evidence count descending, then a stable index.
"""

from __future__ import annotations

from app.schemas.repair import Hypothesis, RootCauseAnalysis

_LABEL_PRIORITY = {"FACT": 0, "INFERENCE": 1, "HYPOTHESIS": 2}


def rank(rca: RootCauseAnalysis) -> list[Hypothesis]:
    indexed = list(enumerate(rca.hypotheses))
    indexed.sort(
        key=lambda pair: (
            _LABEL_PRIORITY.get(pair[1].label, 3),
            pair[1].rank,
            -len(pair[1].evidence),
            pair[0],
        )
    )
    return [h for _i, h in indexed]


def most_likely(rca: RootCauseAnalysis) -> Hypothesis:
    ranked = rank(rca)
    return ranked[0]
