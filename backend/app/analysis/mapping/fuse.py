"""Reciprocal-rank fusion of the per-retriever candidate lists.

``mapping-model v1.0.0`` -- the weights below are the single source of truth's
*copy*; docs/METRICS.md Section 4 is that source. tests/unit/
test_mapping_model_version_sync.py asserts the two stay equal, and any change
here must bump the version + update METRICS.md together (docs/AEGIS_
IMPLEMENTATION_PLAN.md Section 8 regression gate).

Fusion score for a candidate ``c``:
``sum_over_retrievers( w_r / (RRF_K + rank_r(c)) )`` with ``rank_r`` 1-based and
only retrievers that actually returned ``c`` contributing.

``git_history`` and ``memory`` are forward-declared here (weights present, no
retriever yet) the same way Phase 5 forward-declared CHANGED_BY / FIXED_BY edge
types -- they light up in Phase 19 / Phase 20.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aegis.schemas.common import Evidence

from app.analysis.mapping.candidate import RetrieverResult

MAPPING_MODEL_VERSION = "mapping-model v1.0.0"

RRF_K = 60

#: retriever name -> fusion weight. Mirrors docs/METRICS.md Section 4.
MAPPING_MODEL_WEIGHTS: dict[str, float] = {
    "lexical": 1.0,
    "symbol": 0.8,
    "graph": 0.9,
    "git_history": 0.5,
    "memory": 0.6,
    "semantic": 1.0,
}


@dataclass
class FusedCandidate:
    path: str
    score: float
    retrievers: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)


def fuse(results: list[RetrieverResult]) -> list[FusedCandidate]:
    acc: dict[str, FusedCandidate] = {}

    for result in results:
        if not result.available or not result.candidates:
            continue
        weight = MAPPING_MODEL_WEIGHTS.get(result.name)
        if weight is None:
            raise KeyError(
                f"retriever {result.name!r} has no weight in MAPPING_MODEL_WEIGHTS"
            )
        for rank, cand in enumerate(result.candidates, start=1):
            contribution = weight / (RRF_K + rank)
            fc = acc.get(cand.path)
            if fc is None:
                fc = FusedCandidate(path=cand.path, score=0.0)
                acc[cand.path] = fc
            fc.score += contribution
            if result.name not in fc.retrievers:
                fc.retrievers.append(result.name)
            fc.evidence.extend(cand.evidence)
            for sym in cand.symbols:
                if sym not in fc.symbols:
                    fc.symbols.append(sym)

    fused = list(acc.values())
    # Deterministic: score desc, then path asc.
    fused.sort(key=lambda c: (-c.score, c.path))
    return fused
