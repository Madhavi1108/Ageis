"""API-level round trip for the 3 code-graph routes. See
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13 API list. Mirrors
test_analysis_api.py's client fixture exactly.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import app
from app.models.base import Base


@pytest.fixture
def client(tmp_path, acceptance_fixture_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'graph_api_test.db'}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def _get_settings():
        return Settings(
            ingestion_local_roots=[str(acceptance_fixture_path.parent)],
            artifacts_root=str(tmp_path / "artifacts"),
            _env_file=None,
        )

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_settings] = _get_settings
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def _ingest_and_analyze(client, acceptance_fixture_path):
    create_resp = client.post(
        "/repositories", json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)}
    )
    repo_id = create_resp.json()["id"]
    snapshot_resp = client.post(f"/repositories/{repo_id}/snapshots", json={})
    snapshot_id = snapshot_resp.json()["snapshot_id"]
    analysis_resp = client.post(f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis", json={})
    assert analysis_resp.status_code == 201, analysis_resp.text
    return repo_id, snapshot_id


def test_graph_summary_round_trip(client, acceptance_fixture_path):
    repo_id, snapshot_id = _ingest_and_analyze(client, acceptance_fixture_path)

    resp = client.get(f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis/graph")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["node_count"] > 0
    assert body["edge_count"] > 0
    assert body["edges_by_type"]["CALLS"] == 4
    assert body["unresolved_call_count"] == 0
    assert body["graph_artifact_id"] is not None


def test_graph_summary_404_before_analysis(client, acceptance_fixture_path):
    create_resp = client.post(
        "/repositories", json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)}
    )
    repo_id = create_resp.json()["id"]
    snapshot_resp = client.post(f"/repositories/{repo_id}/snapshots", json={})
    snapshot_id = snapshot_resp.json()["snapshot_id"]

    resp = client.get(f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis/graph")
    assert resp.status_code == 404
    assert resp.json()["code"] == "GRAPH_NOT_FOUND"


def test_subgraph_around_calculate_total(client, acceptance_fixture_path):
    repo_id, snapshot_id = _ingest_and_analyze(client, acceptance_fixture_path)

    resp = client.get(
        f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis/graph/subgraph",
        params={"node": "invoice.py::calculate_total", "hops": 1},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["center"]["ref"] == "invoice.py::calculate_total"
    refs = {n["ref"] for n in body["nodes"]}
    assert "checkout.py::process_checkout" in refs
    assert "order_service.py::finalize_order" in refs


def test_subgraph_unknown_node_404s(client, acceptance_fixture_path):
    repo_id, snapshot_id = _ingest_and_analyze(client, acceptance_fixture_path)
    resp = client.get(
        f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis/graph/subgraph",
        params={"node": "nope.py::nothing"},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "GRAPH_NODE_NOT_FOUND"


def test_node_detail_for_calculate_total(client, acceptance_fixture_path):
    repo_id, snapshot_id = _ingest_and_analyze(client, acceptance_fixture_path)

    summary = client.get(f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis/graph").json()
    # Find calculate_total's node id via the subgraph endpoint's center ref.
    sub = client.get(
        f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis/graph/subgraph",
        params={"node": "invoice.py::calculate_total", "hops": 0},
    ).json()
    node_id = sub["center"]["id"]

    resp = client.get(
        f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis/graph/node/{node_id}"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["node"]["ref"] == "invoice.py::calculate_total"
    assert "degree" in body["centrality"]
    assert "betweenness" in body["centrality"]
    incoming_sources = {e["source"]["ref"] for e in body["incoming"]}
    assert "checkout.py::process_checkout" in incoming_sources
    assert "order_service.py::finalize_order" in incoming_sources
    assert summary["node_count"] >= len(body["incoming"]) + len(body["outgoing"])


def test_node_detail_unknown_id_404s(client, acceptance_fixture_path):
    repo_id, snapshot_id = _ingest_and_analyze(client, acceptance_fixture_path)
    resp = client.get(
        f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis/graph/node/does-not-exist"
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "GRAPH_NODE_NOT_FOUND"
