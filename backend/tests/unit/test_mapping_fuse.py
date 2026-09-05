"""Reciprocal-rank fusion math + determinism (docs/METRICS.md Section 4)."""

from __future__ import annotations

import pytest

from aegis.schemas.common import Evidence
from app.analysis.mapping.candidate import RetrievedCandidate, RetrieverResult
from app.analysis.mapping.fuse import (
    MAPPING_MODEL_WEIGHTS,
    RRF_K,
    fuse,
)


def _cand(path: str) -> RetrievedCandidate:
    return RetrievedCandidate(
        path=path,
        score=1.0,
        evidence=[Evidence(kind="file", ref=path, detail="x")],
    )


def test_rrf_score_matches_formula():
    lex = RetrieverResult(name="lexical", candidates=[_cand("a.py"), _cand("b.py")])
    sym = RetrieverResult(name="symbol", candidates=[_cand("b.py")])

    fused = {fc.path: fc for fc in fuse([lex, sym])}

    # a.py: only lexical, rank 1
    assert fused["a.py"].score == pytest.approx(
        MAPPING_MODEL_WEIGHTS["lexical"] / (RRF_K + 1)
    )
    # b.py: lexical rank 2 + symbol rank 1
    expected_b = MAPPING_MODEL_WEIGHTS["lexical"] / (RRF_K + 2) + MAPPING_MODEL_WEIGHTS[
        "symbol"
    ] / (RRF_K + 1)
    assert fused["b.py"].score == pytest.approx(expected_b)
    # b.py beats a.py (two retrievers agree)
    assert fuse([lex, sym])[0].path == "b.py"


def test_unavailable_and_empty_retrievers_contribute_nothing():
    lex = RetrieverResult(name="lexical", candidates=[_cand("a.py")])
    sem = RetrieverResult(name="semantic", candidates=[], available=False)
    graph = RetrieverResult(name="graph", candidates=[])

    fused = fuse([lex, sem, graph])
    assert [fc.path for fc in fused] == ["a.py"]
    assert fused[0].retrievers == ["lexical"]


def test_deterministic_tiebreak_on_path():
    # lexical and semantic share weight 1.0: z.py at rank 1 in one, a.py at
    # rank 1 in the other -> identical fused score -> alphabetical order.
    r1 = RetrieverResult(name="lexical", candidates=[_cand("z.py")])
    r2 = RetrieverResult(name="semantic", candidates=[_cand("a.py")])
    fused = fuse([r1, r2])
    assert fused[0].score == pytest.approx(fused[1].score)
    assert [fc.path for fc in fused] == ["a.py", "z.py"]


def test_unknown_retriever_name_raises():
    bogus = RetrieverResult(name="telepathy", candidates=[_cand("a.py")])
    with pytest.raises(KeyError):
        fuse([bogus])


def test_evidence_and_symbols_merged_across_retrievers():
    c1 = RetrievedCandidate(
        path="a.py",
        score=1.0,
        evidence=[Evidence(kind="file", ref="a.py", detail="lex")],
        symbols=["a.foo"],
    )
    c2 = RetrievedCandidate(
        path="a.py",
        score=1.0,
        evidence=[Evidence(kind="symbol", ref="a.py::foo", detail="sym")],
        symbols=["a.foo", "a.bar"],
    )
    fused = fuse(
        [
            RetrieverResult(name="lexical", candidates=[c1]),
            RetrieverResult(name="symbol", candidates=[c2]),
        ]
    )
    assert len(fused) == 1
    assert len(fused[0].evidence) == 2
    assert fused[0].symbols == ["a.foo", "a.bar"]
