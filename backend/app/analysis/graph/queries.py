"""Query support over a persisted code graph. See
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13: "Provide queries: neighbours,
callers/callees, test-to-code, k-hop impact set, shortest path, centrality."
(centrality itself lives in centrality.py).

Every function here loads the full persisted graph for a snapshot and
rebuilds it with networkx (store.build_networkx) -- fine at this phase's
scale; a caching layer is a later-phase optimization if query latency ever
becomes a real budget concern (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13
lists "query latency within budget" as an integration test, not a Phase 5
caching requirement).
"""
from __future__ import annotations

import networkx as nx
from sqlalchemy.orm import Session

from app.analysis.graph.errors import GraphNodeNotFoundError
from app.analysis.graph.store import build_networkx
from app.models.graph_node import GraphNode
from app.repository.graph import GraphRepository


def _load_graph(session: Session, snapshot_id: str) -> tuple[nx.MultiDiGraph, dict[str, GraphNode]]:
    repo = GraphRepository(session)
    nodes = repo.list_nodes_for_snapshot(snapshot_id)
    edges = repo.list_edges_for_snapshot(snapshot_id)
    graph = build_networkx(nodes, edges)
    node_by_ref = {n.ref: n for n in nodes}
    return graph, node_by_ref


def _require_ref(graph: nx.MultiDiGraph, ref: str, snapshot_id: str) -> None:
    if ref not in graph:
        raise GraphNodeNotFoundError(f"no graph node {ref!r} in snapshot {snapshot_id}")


def callers_of(session: Session, snapshot_id: str, ref: str, *, edge_type: str = "CALLS") -> list[GraphNode]:
    """Nodes with an edge of `edge_type` pointing AT `ref` (default: CALLS,
    i.e. "who calls this symbol")."""
    graph, node_by_ref = _load_graph(session, snapshot_id)
    _require_ref(graph, ref, snapshot_id)
    callers = {
        u for u, _v, d in graph.in_edges(ref, data=True) if d.get("edge_type") == edge_type
    }
    return [node_by_ref[r] for r in sorted(callers) if r in node_by_ref]


def callees_of(session: Session, snapshot_id: str, ref: str, *, edge_type: str = "CALLS") -> list[GraphNode]:
    """Nodes `ref` has an edge of `edge_type` pointing at (default: CALLS,
    i.e. "what this symbol calls")."""
    graph, node_by_ref = _load_graph(session, snapshot_id)
    _require_ref(graph, ref, snapshot_id)
    callees = {
        v for _u, v, d in graph.out_edges(ref, data=True) if d.get("edge_type") == edge_type
    }
    return [node_by_ref[r] for r in sorted(callees) if r in node_by_ref]


def neighbours(session: Session, snapshot_id: str, ref: str) -> list[GraphNode]:
    """All nodes directly connected to `ref` in either direction, any edge type."""
    graph, node_by_ref = _load_graph(session, snapshot_id)
    _require_ref(graph, ref, snapshot_id)
    undirected_neighbours = set(graph.predecessors(ref)) | set(graph.successors(ref))
    return [node_by_ref[r] for r in sorted(undirected_neighbours) if r in node_by_ref]


def k_hop_impact(session: Session, snapshot_id: str, ref: str, k: int = 2) -> list[GraphNode]:
    """Every node reachable from `ref` within `k` hops, following edges in
    either direction (an "impact radius" -- Specification Section 3.4)."""
    graph, node_by_ref = _load_graph(session, snapshot_id)
    _require_ref(graph, ref, snapshot_id)
    undirected = graph.to_undirected(as_view=True)
    lengths = nx.single_source_shortest_path_length(undirected, ref, cutoff=k)
    return [node_by_ref[r] for r in sorted(lengths) if r != ref and r in node_by_ref]


def shortest_path(session: Session, snapshot_id: str, source_ref: str, target_ref: str) -> list[GraphNode] | None:
    graph, node_by_ref = _load_graph(session, snapshot_id)
    _require_ref(graph, source_ref, snapshot_id)
    _require_ref(graph, target_ref, snapshot_id)
    try:
        path = nx.shortest_path(graph, source_ref, target_ref)
    except nx.NetworkXNoPath:
        return None
    return [node_by_ref[r] for r in path if r in node_by_ref]


def subgraph(session: Session, snapshot_id: str, ref: str, hops: int = 1) -> tuple[list[GraphNode], list[tuple[GraphNode, GraphNode, str, str | None]]]:
    """The `ref` node plus everything within `hops`, and the edges among just
    those nodes -- what the GET .../graph/subgraph endpoint returns."""
    graph, node_by_ref = _load_graph(session, snapshot_id)
    _require_ref(graph, ref, snapshot_id)
    undirected = graph.to_undirected(as_view=True)
    lengths = nx.single_source_shortest_path_length(undirected, ref, cutoff=hops)
    included_refs = set(lengths)
    nodes = [node_by_ref[r] for r in sorted(included_refs) if r in node_by_ref]
    edges: list[tuple[GraphNode, GraphNode, str, str | None]] = []
    for u, v, d in graph.edges(data=True):
        if u in included_refs and v in included_refs and u in node_by_ref and v in node_by_ref:
            edges.append((node_by_ref[u], node_by_ref[v], d.get("edge_type"), d.get("confidence")))
    return nodes, edges
