"""Serialize/deserialize + networkx round trip. See
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13 quality gate: "a graph reloaded
from the DB equals the in-memory graph" and "stable node/edge ordering for
determinism."
"""
from __future__ import annotations

from dataclasses import dataclass

from app.analysis.graph.store import build_networkx, graphs_equal, serialize_graph


@dataclass(frozen=True)
class _Node:
    id: str
    node_type: str
    ref: str
    label: str


@dataclass(frozen=True)
class _Edge:
    edge_type: str
    source_node_id: str
    target_node_id: str
    confidence: str | None = None


def _sample():
    nodes = [
        _Node(id="n1", node_type="FILE", ref="a.py", label="a.py"),
        _Node(id="n2", node_type="MODULE", ref="a.py::", label="a.py"),
        _Node(id="n3", node_type="FUNCTION", ref="a.py::foo", label="foo"),
    ]
    edges = [
        _Edge(edge_type="DEFINES", source_node_id="n1", target_node_id="n2"),
        _Edge(edge_type="DEFINES", source_node_id="n2", target_node_id="n3"),
    ]
    return nodes, edges


def test_build_networkx_keys_by_ref_not_id():
    nodes, edges = _sample()
    graph = build_networkx(nodes, edges)
    assert set(graph.nodes) == {"a.py", "a.py::", "a.py::foo"}
    assert graph.has_edge("a.py", "a.py::")
    assert graph.has_edge("a.py::", "a.py::foo")


def test_build_networkx_skips_dangling_edges_without_crashing():
    nodes, _ = _sample()
    dangling = [_Edge(edge_type="DEFINES", source_node_id="n1", target_node_id="does-not-exist")]
    graph = build_networkx(nodes, dangling)
    assert graph.number_of_edges() == 0


def test_serialize_graph_is_sorted_and_deterministic():
    nodes, edges = _sample()
    first = serialize_graph(nodes, edges)
    second = serialize_graph(list(reversed(nodes)), list(reversed(edges)))
    assert first == second  # order of the input lists must not matter


def test_serialize_graph_shape():
    nodes, edges = _sample()
    data = serialize_graph(nodes, edges)
    assert data["nodes"][0] == {"node_type": "FILE", "ref": "a.py", "label": "a.py"}
    assert data["edges"][0]["source_ref"] == "a.py"
    assert data["edges"][0]["target_ref"] == "a.py::"


def test_graphs_equal_is_order_independent():
    nodes, edges = _sample()
    graph_a = build_networkx(nodes, edges)
    graph_b = build_networkx(list(reversed(nodes)), list(reversed(edges)))
    assert graphs_equal(graph_a, graph_b)


def test_graphs_equal_detects_a_real_difference():
    nodes, edges = _sample()
    graph_a = build_networkx(nodes, edges)
    graph_b = build_networkx(nodes, edges[:1])  # missing one edge
    assert not graphs_equal(graph_a, graph_b)
