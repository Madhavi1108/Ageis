"""Heuristic confidence calibration for ``mapping-model v1.0.0``.

Per docs/REPOSITORY_ANALYSIS.md Section 5 / docs/METRICS.md Section 4, v1.0.0
confidence is a heuristic over *cross-retriever agreement* and the *top-score
margin*; a real calibration against a labelled set is Phase 25.

Invariants (asserted by tests/unit/test_mapping_confidence.py):

* **Monotonic in agreement** -- a candidate found by more retrievers never gets
  a lower confidence than the same candidate found by fewer.
* **Semantic penalty** -- when no embeddings retriever is available,
  ``overall_confidence`` is scaled by ``NO_SEMANTIC_FACTOR`` (< 1), reflecting
  the plan's "reports reduced confidence" requirement.
"""

from __future__ import annotations

from app.analysis.mapping.fuse import FusedCandidate

NO_SEMANTIC_FACTOR = 0.85


def candidate_confidence(n_retrievers: int) -> float:
    """1 retriever -> 0.40, 2 -> 0.70, 3 -> 1.00, capped. Strictly increasing
    in ``n_retrievers`` for n >= 1."""
    if n_retrievers <= 0:
        return 0.0
    return round(min(1.0, 0.10 + 0.30 * n_retrievers), 4)


def overall_confidence(
    fused: list[FusedCandidate],
    *,
    semantic_available: bool,
    n_available_retrievers: int,
) -> float:
    if not fused:
        return 0.0

    top = fused[0]
    agreement_frac = len(top.retrievers) / max(1, n_available_retrievers)

    margin = 0.0
    if len(fused) >= 2 and top.score > 0:
        margin = (top.score - fused[1].score) / top.score

    raw = 0.25 + 0.50 * agreement_frac + 0.25 * margin
    if not semantic_available:
        raw *= NO_SEMANTIC_FACTOR
    return round(min(1.0, max(0.0, raw)), 4)
