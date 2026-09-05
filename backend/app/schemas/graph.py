"""API schemas for the code graph. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13.

Plain Pydantic v2 models, matching app/schemas/analysis.py's style.
"""
from __future__ import annotations

from pydantic import BaseModel


class NodeRef(BaseModel):
    id: str
    node_type: str
    ref: str
    label: str


class EdgeRef(BaseModel):
    id: str
    edge_type: str
    source: NodeRef
    target: NodeRef
    confidence: str | None = None


class CodeGraphSummary(BaseModel):
    snapshot_id: str
    node_count: int
    edge_count: int
    nodes_by_type: dict[str, int]
    edges_by_type: dict[str, int]
    unresolved_call_count: int
    graph_artifact_id: str | None


class SubgraphResult(BaseModel):
    center: NodeRef
    hops: int
    nodes: list[NodeRef]
    edges: list[EdgeRef]


class NodeDetail(BaseModel):
    node: NodeRef
    centrality: dict[str, float]
    incoming: list[EdgeRef]
    outgoing: list[EdgeRef]
