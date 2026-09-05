"""Confidence calibration invariants (docs/REPOSITORY_ANALYSIS.md Section 5)."""

from __future__ import annotations

from app.analysis.mapping.confidence import (
    NO_SEMANTIC_FACTOR,
    candidate_confidence,
    overall_confidence,
)
from app.analysis.mapping.fuse import FusedCandidate


def test_candidate_confidence_is_monotonic_in_agreement():
    vals = [candidate_confidence(n) for n in range(1, 6)]
    assert vals == sorted(vals)
    assert all(0.0 <= v <= 1.0 for v in vals)
    # more retrievers agreeing never lowers confidence
    for lo, hi in zip(vals, vals[1:]):
        assert hi >= lo


def test_candidate_confidence_zero_for_no_retrievers():
    assert candidate_confidence(0) == 0.0


def _fused(path: str, score: float, retrievers: list[str]) -> FusedCandidate:
    return FusedCandidate(path=path, score=score, retrievers=retrievers)


def test_overall_confidence_monotonic_in_top_agreement():
    one = [_fused("a.py", 0.05, ["lexical"]), _fused("b.py", 0.04, ["lexical"])]
    three = [
        _fused("a.py", 0.05, ["lexical", "symbol", "graph"]),
        _fused("b.py", 0.04, ["lexical"]),
    ]
    c_one = overall_confidence(one, semantic_available=False, n_available_retrievers=3)
    c_three = overall_confidence(
        three, semantic_available=False, n_available_retrievers=3
    )
    assert c_three >= c_one


def test_missing_semantic_lowers_overall_confidence():
    fused = [
        _fused("a.py", 0.05, ["lexical", "symbol"]),
        _fused("b.py", 0.02, ["lexical"]),
    ]
    with_sem = overall_confidence(
        fused, semantic_available=True, n_available_retrievers=3
    )
    without_sem = overall_confidence(
        fused, semantic_available=False, n_available_retrievers=3
    )
    assert without_sem < with_sem
    assert abs(without_sem - with_sem * NO_SEMANTIC_FACTOR) < 1e-3


def test_empty_fused_is_zero():
    assert (
        overall_confidence([], semantic_available=False, n_available_retrievers=3)
        == 0.0
    )
