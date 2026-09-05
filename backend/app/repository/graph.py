"""Repository pattern for GraphNode/GraphEdge data access. Mirrors
SymbolRepository/DependencyRepository's shape (delete-then-recreate per
snapshot -- a fresh code graph fully replaces the prior one on re-analysis,
same rationale as symbols/dependencies: these are write-once-per-run facts,
not incrementally updated).
"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.analysis.graph.builder import EdgeFact, NodeFact
from app.models.graph_edge import GraphEdge
from app.models.graph_node import GraphNode


class GraphRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_create_nodes(
        self, snapshot_id: str, nodes: list[NodeFact]
    ) -> dict[str, GraphNode]:
        """Returns {ref: GraphNode} so callers can resolve EdgeFact.source_ref/
        target_ref to real row ids without a second query."""
        rows = [
            GraphNode(
                snapshot_id=snapshot_id,
                node_type=n.node_type,
                ref=n.ref,
                label=n.label,
                extra=n.extra,
            )
            for n in nodes
        ]
        self._session.add_all(rows)
        self._session.commit()
        return {row.ref: row for row in rows}

    def bulk_create_edges(
        self, snapshot_id: str, edges: list[EdgeFact], node_id_by_ref: dict[str, GraphNode]
    ) -> list[GraphEdge]:
        rows = []
        for e in edges:
            source = node_id_by_ref.get(e.source_ref)
            target = node_id_by_ref.get(e.target_ref)
            if source is None or target is None:
                # A builder bug would surface here (an edge pointing at a ref
                # that was never added as a node) -- skip rather than crash
                # the whole persist step over one bad edge.
                continue
            rows.append(
                GraphEdge(
                    snapshot_id=snapshot_id,
                    edge_type=e.edge_type,
                    source_node_id=source.id,
                    target_node_id=target.id,
                    confidence=e.confidence,
                    evidence=e.evidence,
                )
            )
        self._session.add_all(rows)
        self._session.commit()
        return rows

    def replace_for_snapshot(
        self, snapshot_id: str, nodes: list[NodeFact], edges: list[EdgeFact]
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        self._session.execute(delete(GraphEdge).where(GraphEdge.snapshot_id == snapshot_id))
        self._session.execute(delete(GraphNode).where(GraphNode.snapshot_id == snapshot_id))
        self._session.commit()
        node_by_ref = self.bulk_create_nodes(snapshot_id, nodes)
        edge_rows = self.bulk_create_edges(snapshot_id, edges, node_by_ref)
        return list(node_by_ref.values()), edge_rows

    def list_nodes_for_snapshot(
        self, snapshot_id: str, *, node_type: str | None = None, limit: int = 50_000
    ) -> list[GraphNode]:
        stmt = select(GraphNode).where(GraphNode.snapshot_id == snapshot_id)
        if node_type is not None:
            stmt = stmt.where(GraphNode.node_type == node_type)
        stmt = stmt.order_by(GraphNode.ref).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def list_edges_for_snapshot(
        self, snapshot_id: str, *, edge_type: str | None = None, limit: int = 200_000
    ) -> list[GraphEdge]:
        stmt = select(GraphEdge).where(GraphEdge.snapshot_id == snapshot_id)
        if edge_type is not None:
            stmt = stmt.where(GraphEdge.edge_type == edge_type)
        stmt = stmt.order_by(GraphEdge.edge_type, GraphEdge.source_node_id).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def get_node_by_ref(self, snapshot_id: str, ref: str) -> GraphNode | None:
        stmt = select(GraphNode).where(
            GraphNode.snapshot_id == snapshot_id, GraphNode.ref == ref
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._session.get(GraphNode, node_id)
