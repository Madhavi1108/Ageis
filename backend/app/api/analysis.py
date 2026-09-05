"""Repository analysis API. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 12.

Nested under /repositories/{id}/snapshots/{snapshot_id}, consistent with Phase 3's
existing URL shape for snapshots.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analysis.analyze import analyze_snapshot, build_analysis_result
from app.analysis.errors import AnalysisNotFoundError, SnapshotNotFoundError
from app.analysis.graph import queries as graph_queries
from app.analysis.graph.centrality import compute_centrality
from app.analysis.graph.errors import GraphNodeNotFoundError, GraphNotFoundError
from app.analysis.graph.store import build_networkx
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.repository.analyses import AnalysisRepository
from app.repository.graph import GraphRepository
from app.repository.snapshots import SnapshotRepository
from app.schemas.analysis import AnalyzeRequest, RepositoryAnalysisResult
from app.schemas.graph import CodeGraphSummary, EdgeRef, NodeDetail, NodeRef, SubgraphResult

router = APIRouter(prefix="/repositories", tags=["analysis"])


def _get_snapshot_or_404(db: Session, repository_id: str, snapshot_id: str):
    snapshot = SnapshotRepository(db).get(snapshot_id)
    if snapshot is None or snapshot.repository_id != repository_id:
        raise SnapshotNotFoundError(
            f"snapshot {snapshot_id} not found for repository {repository_id}"
        )
    return snapshot


@router.post(
    "/{repository_id}/snapshots/{snapshot_id}/analysis",
    status_code=201,
    response_model=RepositoryAnalysisResult,
)
def create_analysis(
    repository_id: str,
    snapshot_id: str,
    body: AnalyzeRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RepositoryAnalysisResult:
    snapshot = _get_snapshot_or_404(db, repository_id, snapshot_id)
    return analyze_snapshot(db, snapshot=snapshot, settings=settings, force=body.force)


@router.get(
    "/{repository_id}/snapshots/{snapshot_id}/analysis",
    response_model=RepositoryAnalysisResult,
)
def get_analysis(
    repository_id: str, snapshot_id: str, db: Session = Depends(get_db)
) -> RepositoryAnalysisResult:
    _get_snapshot_or_404(db, repository_id, snapshot_id)
    analysis = AnalysisRepository(db).get_by_snapshot(snapshot_id)
    if analysis is None:
        raise AnalysisNotFoundError(
            f"no analysis recorded yet for snapshot {snapshot_id}"
        )
    # job_id isn't tracked on the RepositoryAnalysis row itself (it belongs to the Job
    # that produced it); GET has no fresh job to report, so this is left empty.
    return build_analysis_result(analysis, job_id="")


def _to_node_ref(node) -> NodeRef:
    return NodeRef(id=node.id, node_type=node.node_type, ref=node.ref, label=node.label)


@router.get(
    "/{repository_id}/snapshots/{snapshot_id}/analysis/graph",
    response_model=CodeGraphSummary,
)
def get_graph_summary(
    repository_id: str, snapshot_id: str, db: Session = Depends(get_db)
) -> CodeGraphSummary:
    """See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13 API list."""
    _get_snapshot_or_404(db, repository_id, snapshot_id)
    graph_repo = GraphRepository(db)
    nodes = graph_repo.list_nodes_for_snapshot(snapshot_id)
    if not nodes:
        raise GraphNotFoundError(f"no code graph built yet for snapshot {snapshot_id}")
    edges = graph_repo.list_edges_for_snapshot(snapshot_id)
    analysis = AnalysisRepository(db).get_by_snapshot(snapshot_id)

    nodes_by_type: dict[str, int] = {}
    for n in nodes:
        nodes_by_type[n.node_type] = nodes_by_type.get(n.node_type, 0) + 1
    edges_by_type: dict[str, int] = {}
    unresolved = 0
    for e in edges:
        edges_by_type[e.edge_type] = edges_by_type.get(e.edge_type, 0) + 1
        if e.edge_type == "CALLS" and e.confidence == "UNRESOLVED":
            unresolved += 1

    return CodeGraphSummary(
        snapshot_id=snapshot_id,
        node_count=len(nodes),
        edge_count=len(edges),
        nodes_by_type=nodes_by_type,
        edges_by_type=edges_by_type,
        unresolved_call_count=unresolved,
        graph_artifact_id=analysis.graph_artifact_id if analysis else None,
    )


@router.get(
    "/{repository_id}/snapshots/{snapshot_id}/analysis/graph/subgraph",
    response_model=SubgraphResult,
)
def get_subgraph(
    repository_id: str,
    snapshot_id: str,
    node: str,
    hops: int = 1,
    db: Session = Depends(get_db),
) -> SubgraphResult:
    _get_snapshot_or_404(db, repository_id, snapshot_id)
    graph_repo = GraphRepository(db)
    center = graph_repo.get_node_by_ref(snapshot_id, node)
    if center is None:
        raise GraphNodeNotFoundError(f"no graph node {node!r} in snapshot {snapshot_id}")
    nodes, edges = graph_queries.subgraph(db, snapshot_id, node, hops=hops)
    return SubgraphResult(
        center=_to_node_ref(center),
        hops=hops,
        nodes=[_to_node_ref(n) for n in nodes],
        edges=[
            EdgeRef(
                id=f"{u.id}:{v.id}:{et}",
                edge_type=et,
                source=_to_node_ref(u),
                target=_to_node_ref(v),
                confidence=conf,
            )
            for u, v, et, conf in edges
        ],
    )


@router.get(
    "/{repository_id}/snapshots/{snapshot_id}/analysis/graph/node/{node_id}",
    response_model=NodeDetail,
)
def get_graph_node(
    repository_id: str, snapshot_id: str, node_id: str, db: Session = Depends(get_db)
) -> NodeDetail:
    _get_snapshot_or_404(db, repository_id, snapshot_id)
    graph_repo = GraphRepository(db)
    node = graph_repo.get_node(node_id)
    if node is None or node.snapshot_id != snapshot_id:
        raise GraphNodeNotFoundError(f"no graph node {node_id!r} in snapshot {snapshot_id}")

    nodes = graph_repo.list_nodes_for_snapshot(snapshot_id)
    edges = graph_repo.list_edges_for_snapshot(snapshot_id)
    graph = build_networkx(nodes, edges)
    centrality = compute_centrality(graph).get(node.ref, {"degree": 0.0, "betweenness": 0.0})

    node_by_id = {n.id: n for n in nodes}
    incoming = [
        EdgeRef(
            id=e.id,
            edge_type=e.edge_type,
            source=_to_node_ref(node_by_id[e.source_node_id]),
            target=_to_node_ref(node_by_id[e.target_node_id]),
            confidence=e.confidence,
        )
        for e in edges
        if e.target_node_id == node.id and e.source_node_id in node_by_id
    ]
    outgoing = [
        EdgeRef(
            id=e.id,
            edge_type=e.edge_type,
            source=_to_node_ref(node_by_id[e.source_node_id]),
            target=_to_node_ref(node_by_id[e.target_node_id]),
            confidence=e.confidence,
        )
        for e in edges
        if e.source_node_id == node.id and e.target_node_id in node_by_id
    ]
    return NodeDetail(
        node=_to_node_ref(node), centrality=centrality, incoming=incoming, outgoing=outgoing
    )
