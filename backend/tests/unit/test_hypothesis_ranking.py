"""Hypothesis ranking: label priority, then model rank, then evidence count."""

from __future__ import annotations

from aegis.schemas.common import Confidence, Evidence
from app.debugging.hypotheses import most_likely, rank
from app.schemas.repair import Hypothesis, RootCauseAnalysis


def _h(statement, label, rank_=0, ev=0):
    return Hypothesis(
        statement=statement,
        label=label,
        rank=rank_,
        evidence=[Evidence(kind="test", ref="t", detail="d") for _ in range(ev)],
    )


def _rca(hyps):
    return RootCauseAnalysis(
        hypotheses=hyps,
        most_likely_index=0,
        confidence=Confidence(value=0.5, basis="INFERENCE"),
    )


def test_fact_beats_inference_beats_hypothesis():
    rca = _rca([_h("h", "HYPOTHESIS"), _h("i", "INFERENCE"), _h("f", "FACT")])
    assert [x.statement for x in rank(rca)] == ["f", "i", "h"]
    assert most_likely(rca).label == "FACT"


def test_tiebreak_on_model_rank_then_evidence():
    rca = _rca(
        [
            _h("a", "INFERENCE", rank_=2, ev=5),
            _h("b", "INFERENCE", rank_=1, ev=0),
            _h("c", "INFERENCE", rank_=1, ev=3),
        ]
    )
    assert [x.statement for x in rank(rca)] == ["c", "b", "a"]


def test_stable_for_equal_keys():
    rca = _rca([_h("first", "FACT"), _h("second", "FACT")])
    assert [x.statement for x in rank(rca)] == ["first", "second"]
