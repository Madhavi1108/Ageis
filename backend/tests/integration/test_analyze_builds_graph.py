"""The code graph, built for real during analyze_snapshot() against the
acceptance repo. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13
"Integration"/"Acceptance" tests: golden edge set, DB-reload equality, and
the Specification's own worked example ("callers of calculate_total returns
checkout and order_service").
"""
from __future__ import annotations

import pytest

from app.analysis.analyze import analyze_snapshot
from app.analysis.graph import queries
from app.analysis.graph.errors import GraphNodeNotFoundError
from app.analysis.graph.store import build_networkx, graphs_equal
from app.ingestion.ingest import ingest_repository
from app.repository.analyses import AnalysisRepository
from app.repository.graph import GraphRepository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.schemas.repository import IngestRequest


def _analyze_acceptance(db_session, ingestion_settings, acceptance_fixture_path):
    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL", url_or_path=str(acceptance_fixture_path), name="aegis-acceptance"
    )
    ingest_result = ingest_repository(
        db_session, repository=repo, request=IngestRequest(), settings=ingestion_settings
    )
    snapshot = SnapshotRepository(db_session).get(ingest_result.snapshot_id)
    analyze_snapshot(db_session, snapshot=snapshot, settings=ingestion_settings)
    return snapshot


def test_graph_artifact_is_linked_from_the_analysis_row(
    db_session, ingestion_settings, acceptance_fixture_path
):
    snapshot = _analyze_acceptance(db_session, ingestion_settings, acceptance_fixture_path)
    analysis = AnalysisRepository(db_session).get_by_snapshot(snapshot.id)
    assert analysis.graph_artifact_id is not None


def test_callers_of_calculate_total_are_checkout_and_order_service(
    db_session, ingestion_settings, acceptance_fixture_path
):
    """The Specification's own worked example (Section 10), made real."""
    snapshot = _analyze_acceptance(db_session, ingestion_settings, acceptance_fixture_path)

    callers = queries.callers_of(db_session, snapshot.id, "invoice.py::calculate_total")
    caller_files = {c.extra["file"] for c in callers}

    assert "checkout.py" in caller_files
    assert "order_service.py" in caller_files
    for c in callers:
        assert c.node_type in ("FUNCTION", "TEST")


def test_golden_edge_set_for_the_acceptance_repo(
    db_session, ingestion_settings, acceptance_fixture_path
):
    snapshot = _analyze_acceptance(db_session, ingestion_settings, acceptance_fixture_path)
    graph_repo = GraphRepository(db_session)
    nodes = graph_repo.list_nodes_for_snapshot(snapshot.id)
    edges = graph_repo.list_edges_for_snapshot(snapshot.id)
    node_by_id = {n.id: n for n in nodes}

    calls = {
        (node_by_id[e.source_node_id].ref, node_by_id[e.target_node_id].ref, e.confidence)
        for e in edges
        if e.edge_type == "CALLS"
    }
    assert ("checkout.py::process_checkout", "invoice.py::calculate_total", "RESOLVED") in calls
    assert ("order_service.py::finalize_order", "invoice.py::calculate_total", "RESOLVED") in calls
    # No CALLS edge in this fixture is unresolved -- every call target is a
    # real, locally-defined symbol.
    assert all(e.confidence != "UNRESOLVED" for e in edges if e.edge_type == "CALLS")

    tests_edges = {
        (node_by_id[e.source_node_id].ref, node_by_id[e.target_node_id].ref)
        for e in edges
        if e.edge_type == "TESTS"
    }
    assert ("test_invoice.py", "invoice.py") in tests_edges


def test_reloaded_graph_equals_in_memory_graph(
    db_session, ingestion_settings, acceptance_fixture_path
):
    """docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13 quality gate."""
    snapshot = _analyze_acceptance(db_session, ingestion_settings, acceptance_fixture_path)
    graph_repo = GraphRepository(db_session)

    nodes_first = graph_repo.list_nodes_for_snapshot(snapshot.id)
    edges_first = graph_repo.list_edges_for_snapshot(snapshot.id)
    graph_first = build_networkx(nodes_first, edges_first)

    # Reload independently (fresh queries -- proves it's not just the same
    # Python objects being compared with themselves).
    nodes_second = graph_repo.list_nodes_for_snapshot(snapshot.id)
    edges_second = graph_repo.list_edges_for_snapshot(snapshot.id)
    graph_second = build_networkx(nodes_second, edges_second)

    assert graphs_equal(graph_first, graph_second)


def test_k_hop_impact_from_calculate_total_includes_its_callers(
    db_session, ingestion_settings, acceptance_fixture_path
):
    snapshot = _analyze_acceptance(db_session, ingestion_settings, acceptance_fixture_path)
    impacted = queries.k_hop_impact(db_session, snapshot.id, "invoice.py::calculate_total", k=1)
    impacted_refs = {n.ref for n in impacted}
    assert "checkout.py::process_checkout" in impacted_refs
    assert "order_service.py::finalize_order" in impacted_refs


def test_callees_of_process_checkout_includes_calculate_total(
    db_session, ingestion_settings, acceptance_fixture_path
):
    snapshot = _analyze_acceptance(db_session, ingestion_settings, acceptance_fixture_path)
    callees = queries.callees_of(db_session, snapshot.id, "checkout.py::process_checkout")
    assert {c.ref for c in callees} == {"invoice.py::calculate_total"}


def test_neighbours_of_invoice_module_includes_its_function(
    db_session, ingestion_settings, acceptance_fixture_path
):
    snapshot = _analyze_acceptance(db_session, ingestion_settings, acceptance_fixture_path)
    neighbours = queries.neighbours(db_session, snapshot.id, "invoice.py")
    refs = {n.ref for n in neighbours}
    assert "invoice.py::" in refs  # FILE -DEFINES-> MODULE


def test_shortest_path_from_checkout_function_to_calculate_total(
    db_session, ingestion_settings, acceptance_fixture_path
):
    snapshot = _analyze_acceptance(db_session, ingestion_settings, acceptance_fixture_path)
    path = queries.shortest_path(
        db_session, snapshot.id, "checkout.py::process_checkout", "invoice.py::calculate_total"
    )
    assert path is not None
    refs = [n.ref for n in path]
    assert refs[0] == "checkout.py::process_checkout"
    assert refs[-1] == "invoice.py::calculate_total"


def test_shortest_path_unreachable_returns_none(
    db_session, ingestion_settings, acceptance_fixture_path
):
    """utils.py::format_currency is never called by anything and calls
    nothing local -- no path should connect it to invoice.py's symbols."""
    snapshot = _analyze_acceptance(db_session, ingestion_settings, acceptance_fixture_path)
    path = queries.shortest_path(
        db_session, snapshot.id, "utils.py::format_currency", "invoice.py::calculate_total"
    )
    assert path is None


def test_query_on_unknown_ref_raises_graph_node_not_found(
    db_session, ingestion_settings, acceptance_fixture_path
):
    snapshot = _analyze_acceptance(db_session, ingestion_settings, acceptance_fixture_path)
    with pytest.raises(GraphNodeNotFoundError):
        queries.callers_of(db_session, snapshot.id, "does-not-exist.py::nothing")
