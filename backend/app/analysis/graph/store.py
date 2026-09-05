"""NetworkX construction and JSON (de)serialization for the code graph. See
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13: "persist edges for querying and
keep NetworkX for algorithms" and the quality gate "a graph reloaded from the
DB equals the in-memory graph."

Operates on already-persisted GraphNode/GraphEdge rows (or any object with
the same shape, matched via Protocol so tests need no DB session) --
GraphEdge stores `source_node_id`/`target_node_id` (a DB foreign key, correct
for relational storage), while the graph itself is built and compared keyed
by each node's stable `ref` string (a symbol_id / file path / "dep::..." --
stable across a build/persist/reload round trip, unlike a DB-assigned row
id). Every function here does that id->ref translation once, from the same
`nodes` list the caller already has.
"""
from __future__ import annotations

from typing import Protocol

import networkx as nx


class NodeLike(Protocol):
    id: str
    node_type: str
    ref: str
    label: str


class EdgeLike(Protocol):
    edge_type: str
    source_node_id: str
    target_node_id: str
    confidence: str | None


def _ref_by_id(nodes: list[NodeLike]) -> dict[str, str]:
    return {n.id: n.ref for n in nodes}


def build_networkx(nodes: list[NodeLike], edges: list[EdgeLike]) -> nx.MultiDiGraph:
    """Build a graph keyed by each node's `ref`."""
    graph: nx.MultiDiGraph = nx.MultiDiGraph()
    for n in nodes:
        graph.add_node(n.ref, node_type=n.node_type, label=n.label)
    ref_by_id = _ref_by_id(nodes)
    for e in edges:
        source_ref = ref_by_id.get(e.source_node_id)
        target_ref = ref_by_id.get(e.target_node_id)
        if source_ref is None or target_ref is None:
            continue  # a dangling edge would indicate a persistence bug, not a graph fact
        graph.add_edge(source_ref, target_ref, edge_type=e.edge_type, confidence=e.confidence)
    return graph


def serialize_graph(nodes: list[NodeLike], edges: list[EdgeLike]) -> dict:
    """A plain-JSON representation for the GRAPH-kind Artifact blob. Sorted so
    two builds of the same graph produce byte-identical output (the plan's
    regression requirement: "stable node/edge ordering for determinism")."""
    ref_by_id = _ref_by_id(nodes)
    edge_dicts = []
    for e in edges:
        source_ref = ref_by_id.get(e.source_node_id)
        target_ref = ref_by_id.get(e.target_node_id)
        if source_ref is None or target_ref is None:
            continue
        edge_dicts.append(
            {
                "edge_type": e.edge_type,
                "source_ref": source_ref,
                "target_ref": target_ref,
                "confidence": e.confidence,
            }
        )
    return {
        "nodes": sorted(
            (
                {"node_type": n.node_type, "ref": n.ref, "label": n.label}
                for n in nodes
            ),
            key=lambda n: (n["node_type"], n["ref"]),
        ),
        "edges": sorted(
            edge_dicts, key=lambda e: (e["edge_type"], e["source_ref"], e["target_ref"])
        ),
    }


def graphs_equal(a: nx.MultiDiGraph, b: nx.MultiDiGraph) -> bool:
    """Order-independent equality: same node set, same (source, target,
    edge_type) triples. Used to prove "reloaded from the DB equals the
    in-memory graph" without depending on iteration order."""
    if set(a.nodes) != set(b.nodes):
        return False
    edges_a = {(u, v, d.get("edge_type")) for u, v, d in a.edges(data=True)}
    edges_b = {(u, v, d.get("edge_type")) for u, v, d in b.edges(data=True)}
    return edges_a == edges_b
