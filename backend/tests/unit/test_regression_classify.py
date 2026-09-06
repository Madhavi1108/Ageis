"""Regression classifier: TARGETED / RELATED / REGRESSION / FULL + rationale."""

from __future__ import annotations

import networkx as nx

from app.testing.regression import CorpusTest, classify


def _graph():
    # file graph: m.py -> n.py -> o.py ; hub.py is central
    g = nx.MultiDiGraph()
    for u, v in [
        ("m.py", "n.py"),
        ("n.py", "o.py"),
        ("a.py", "hub.py"),
        ("b.py", "hub.py"),
        ("hub.py", "c.py"),
    ]:
        g.add_edge(u, v, edge_type="IMPORTS")
    return g


def _classify(corpus, **over):
    kw = dict(
        corpus=corpus,
        changed_files={"m.py"},
        changed_symbols={"m.py::f"},
        graph=_graph(),
        centrality={
            "hub.py": {"betweenness": 0.9, "degree": 0.5},
            "m.py": {"betweenness": 0.0, "degree": 0.2},
            "n.py": {"betweenness": 0.1, "degree": 0.2},
        },
        prior_failure_files=set(),
        related_hops=2,
        centrality_decile=0.9,
    )
    kw.update(over)
    return {c.test_id: c for c in classify(**kw)}


def test_direct_cover_is_targeted():
    res = _classify(
        [
            CorpusTest(
                "test_m.py::test_f", "test_m.py", frozenset({"m.py"}), None, False
            ),
        ]
    )
    c = res["test_m.py::test_f"]
    assert c.classification == "TARGETED"
    assert c.rationale
    assert c.hops == 0


def test_generated_target_symbol_is_targeted():
    res = _classify(
        [
            CorpusTest(
                "t.py::t_boundary", "t.py", frozenset({"m.py"}), "m.py::f", True
            ),
        ]
    )
    assert res["t.py::t_boundary"].classification == "TARGETED"
    assert res["t.py::t_boundary"].covers_symbol == "m.py::f"


def test_name_targeting_a_changed_module_is_targeted():
    res = _classify(
        [
            CorpusTest("test_m.py", "test_m.py", frozenset(), None, False),
        ]
    )
    assert res["test_m.py"].classification == "TARGETED"


def test_k_hop_neighbour_is_related():
    res = _classify(
        [
            CorpusTest("test_o.py::t", "test_o.py", frozenset({"o.py"}), None, False),
        ]
    )
    c = res["test_o.py::t"]
    assert c.classification == "RELATED"
    assert c.hops == 2


def test_high_centrality_cover_is_regression():
    res = _classify(
        [
            CorpusTest(
                "test_hub.py::t", "test_hub.py", frozenset({"hub.py"}), None, False
            ),
        ]
    )
    assert res["test_hub.py::t"].classification == "REGRESSION"
    assert "centrality" in res["test_hub.py::t"].rationale


def test_prior_failure_file_is_regression():
    res = _classify(
        [CorpusTest("test_far.py::t", "test_far.py", frozenset({"c.py"}), None, False)],
        prior_failure_files={"test_far.py"},
    )
    assert res["test_far.py::t"].classification == "REGRESSION"


def test_unrelated_is_full_and_output_is_sorted():
    res = classify(
        corpus=[
            CorpusTest("test_z.py::t", "test_z.py", frozenset({"c.py"}), None, False),
            CorpusTest("test_m.py::t", "test_m.py", frozenset({"m.py"}), None, False),
        ],
        changed_files={"m.py"},
        changed_symbols=set(),
        graph=_graph(),
        centrality={},
        prior_failure_files=set(),
        related_hops=2,
        centrality_decile=0.9,
    )
    assert [c.classification for c in res] == ["TARGETED", "FULL"]  # sorted by rank
    assert res[-1].rationale
