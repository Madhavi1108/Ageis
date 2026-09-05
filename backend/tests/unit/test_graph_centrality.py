"""Centrality on a hand-computed small graph. See
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13 "Unit: ... centrality on a
hand-computed small graph."
"""
from __future__ import annotations

import networkx as nx

from app.analysis.graph.centrality import compute_centrality


def test_three_node_path_betweenness_and_degree():
    """A -> B -> C: B sits on the only path between A and C, so it has the
    maximum betweenness in the graph (0.5 -- networkx normalizes a directed
    graph's betweenness by 1/((n-1)(n-2)), not the undirected 2/((n-1)(n-2)),
    so a single unique routing path yields 0.5 here, not 1.0) and A/C have 0.
    Degree centrality is highest for B too.
    """
    graph = nx.MultiDiGraph()
    graph.add_edge("A", "B", edge_type="CALLS", confidence="RESOLVED")
    graph.add_edge("B", "C", edge_type="CALLS", confidence="RESOLVED")

    centrality = compute_centrality(graph)

    assert centrality["B"]["betweenness"] == 0.5
    assert centrality["A"]["betweenness"] == 0.0
    assert centrality["C"]["betweenness"] == 0.0
    assert centrality["B"]["degree"] > centrality["A"]["degree"]
    assert centrality["B"]["degree"] > centrality["C"]["degree"]


def test_star_graph_center_has_max_betweenness():
    """A hub-and-spoke graph: the center sits on every shortest path between
    any two spokes, so it has the maximum possible betweenness; a leaf has
    zero (nothing routes through a leaf)."""
    graph = nx.MultiDiGraph()
    for leaf in ("L1", "L2", "L3", "L4"):
        graph.add_edge("HUB", leaf, edge_type="CALLS", confidence="RESOLVED")
        graph.add_edge(leaf, "HUB", edge_type="CALLS", confidence="RESOLVED")

    centrality = compute_centrality(graph)

    assert centrality["HUB"]["betweenness"] > 0.0
    assert centrality["L1"]["betweenness"] == 0.0
    assert centrality["HUB"]["betweenness"] == max(c["betweenness"] for c in centrality.values())


def test_empty_graph_returns_empty_dict():
    assert compute_centrality(nx.MultiDiGraph()) == {}


def test_single_node_graph_does_not_crash():
    """networkx special-cases a 1-node graph for degree_centrality (dividing
    by n-1=0 would otherwise be a ZeroDivisionError), returning degree=1 by
    convention; betweenness is 0 (no pair of other nodes to route between)."""
    graph = nx.MultiDiGraph()
    graph.add_node("LONELY")
    centrality = compute_centrality(graph)
    assert centrality["LONELY"]["betweenness"] == 0.0
    assert centrality["LONELY"]["degree"] == 1


def test_isolated_node_among_others_has_zero_degree():
    graph = nx.MultiDiGraph()
    graph.add_edge("A", "B", edge_type="CALLS", confidence="RESOLVED")
    graph.add_node("ISOLATED")
    centrality = compute_centrality(graph)
    assert centrality["ISOLATED"] == {"degree": 0.0, "betweenness": 0.0}
