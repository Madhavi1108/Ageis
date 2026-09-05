"""Centrality metrics for the code graph. See
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13: "degree + (approximate for
large graphs) betweenness centrality feed the risk score" (the risk score
itself is Phase 17's job -- this module only computes the graph-theoretic
values).
"""
from __future__ import annotations

import networkx as nx

# Above this many nodes, betweenness centrality is estimated from a random
# sample of source nodes (networkx's `k` parameter) rather than computed
# exactly, which is O(n * edges) and too slow at scale. Below it, exact.
_BETWEENNESS_EXACT_NODE_LIMIT = 500
_BETWEENNESS_SAMPLE_K = 100
_BETWEENNESS_SEED = 0  # deterministic sampling, matching the plan's replay/determinism goals


def compute_centrality(graph: nx.MultiDiGraph) -> dict[str, dict[str, float]]:
    """Returns {node_ref: {"degree": float, "betweenness": float}}."""
    if graph.number_of_nodes() == 0:
        return {}

    simple = nx.DiGraph(graph)  # betweenness_centrality doesn't support MultiDiGraph directly
    degree = nx.degree_centrality(simple)

    if simple.number_of_nodes() > _BETWEENNESS_EXACT_NODE_LIMIT:
        betweenness = nx.betweenness_centrality(
            simple, k=min(_BETWEENNESS_SAMPLE_K, simple.number_of_nodes()), seed=_BETWEENNESS_SEED
        )
    else:
        betweenness = nx.betweenness_centrality(simple)

    return {
        ref: {"degree": degree.get(ref, 0.0), "betweenness": betweenness.get(ref, 0.0)}
        for ref in graph.nodes
    }
