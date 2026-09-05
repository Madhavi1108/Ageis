"""The "no evidence-free candidate" rule is enforced structurally
(docs/REPOSITORY_ANALYSIS.md Section 5)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aegis.schemas.common import Evidence
from app.analysis.mapping.evidence import to_candidates
from app.analysis.mapping.fuse import FusedCandidate
from app.schemas.mapping import MappingCandidate


def test_mapping_candidate_rejects_empty_evidence():
    with pytest.raises(ValidationError):
        MappingCandidate(path="a.py", score=1.0, confidence=0.5, evidence=[])


def test_to_candidates_drops_evidence_free_fused_entries():
    good = FusedCandidate(
        path="a.py",
        score=0.5,
        retrievers=["lexical", "symbol"],
        evidence=[Evidence(kind="file", ref="a.py", detail="hit")],
    )
    bad = FusedCandidate(path="b.py", score=0.9, retrievers=["lexical"], evidence=[])
    out = to_candidates([bad, good], threshold=0.0, top_k=10)
    assert [c.path for c in out] == ["a.py"]


def test_to_candidates_applies_confidence_threshold():
    single = FusedCandidate(
        path="a.py",
        score=0.5,
        retrievers=["lexical"],  # -> candidate_confidence(1) == 0.40
        evidence=[Evidence(kind="file", ref="a.py", detail="hit")],
    )
    assert to_candidates([single], threshold=0.5, top_k=10) == []
    assert len(to_candidates([single], threshold=0.3, top_k=10)) == 1


def test_graph_only_candidate_is_labelled_inference():
    graph_only = FusedCandidate(
        path="a.py",
        score=0.5,
        retrievers=["graph"],
        evidence=[Evidence(kind="file", ref="a.py", detail="2 hops")],
    )
    [cand] = to_candidates([graph_only], threshold=0.0, top_k=10)
    assert cand.labels == ["INFERENCE"]


def test_lexical_candidate_is_labelled_fact():
    lex = FusedCandidate(
        path="a.py",
        score=0.5,
        retrievers=["lexical", "graph"],
        evidence=[Evidence(kind="file", ref="a.py", detail="hit")],
    )
    [cand] = to_candidates([lex], threshold=0.0, top_k=10)
    assert "FACT" in cand.labels
    assert "INFERENCE" in cand.labels
