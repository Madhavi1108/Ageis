"""Reverse-graph BFS blast radius: depth control + hop grouping."""

from __future__ import annotations

import networkx as nx

from app.analysis.impact import _blast_radius


def _chain() -> nx.MultiDiGraph:
    # a -> b -> c -> d  (edge direction = "calls"); reverse BFS from `d` should
    # reach c at hop 1, b at hop 2, a at hop 3.
    g = nx.MultiDiGraph()
    for u, v in [("a", "b"), ("b", "c"), ("c", "d")]:
        g.add_edge(u, v, edge_type="CALLS")
    return g


def test_hop_grouping_follows_reverse_edges():
    radius = _blast_radius(_chain(), ["d"], hops=3)
    assert radius == {"1": ["c"], "2": ["b"], "3": ["a"]}


def test_cutoff_respected():
    radius = _blast_radius(_chain(), ["d"], hops=1)
    assert radius == {"1": ["c"]}


def test_seed_itself_is_excluded():
    radius = _blast_radius(_chain(), ["d"], hops=3)
    flat = [r for refs in radius.values() for r in refs]
    assert "d" not in flat


def test_multiple_seeds_take_min_distance():
    g = _chain()
    # from both `d` and `c`: `b` is hop 2 from d but hop 1 from c -> hop 1 wins
    radius = _blast_radius(g, ["d", "c"], hops=3)
    assert "b" in radius["1"]
    assert all("b" not in refs for k, refs in radius.items() if k != "1")


def test_unknown_seed_is_ignored():
    assert _blast_radius(_chain(), ["not-a-node"], hops=3) == {}


def test_no_seeds():
    assert _blast_radius(_chain(), [], hops=3) == {}
