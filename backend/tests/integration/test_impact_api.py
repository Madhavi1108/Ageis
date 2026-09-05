"""Phase 8 integration: impact analysis over the real aegis-acceptance fixture.

See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 16 "Phase-wise testing".
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
    engine = create_engine(f"sqlite:///{tmp_path / 'impact_test.db'}")
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
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def _task_with_mapping(client, acceptance_fixture_path) -> str:
    repo_id = client.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)},
    ).json()["id"]
    snapshot_id = client.post(f"/repositories/{repo_id}/snapshots", json={}).json()[
        "snapshot_id"
    ]
    assert (
        client.post(
            f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis", json={}
        ).status_code
        == 201
    )
    task_md = (acceptance_fixture_path / "task.md").read_text(encoding="utf-8")
    task_id = client.post(
        "/tasks", json={"repository_id": repo_id, "text": task_md}
    ).json()["task"]["id"]
    assert client.post("/analysis/map", json={"task_id": task_id}).status_code == 201
    return task_id


def test_impact_report_matches_specification_example(client, acceptance_fixture_path):
    task_id = _task_with_mapping(client, acceptance_fixture_path)

    r = client.get(f"/tasks/{task_id}/impact")
    assert r.status_code == 200, r.text
    impact = r.json()

    assert "invoice.py" in impact["changed_set"]["files"]
    assert "invoice.py::calculate_total" in impact["changed_set"]["symbols"]

    caller_refs = {c["ref"] for entry in impact["callers"] for c in entry["callers"]}
    assert "checkout.py::process_checkout" in caller_refs
    assert "order_service.py::finalize_order" in caller_refs

    assert "test_invoice.py" in impact["related_tests"]

    bundle = impact["risk_signal_bundle"]
    assert bundle["architectural_centrality"]["value"] is not None
    assert bundle["architectural_centrality"]["basis"] == "FACT"
    assert bundle["inverse_coverage"]["value"] is None
    assert bundle["inverse_coverage"]["unavailable_reason"]
    assert bundle["files_changed"]["value"] >= 1.0

    assert "calculate_total" in impact["report"]
    assert impact["task_id"] == task_id


def test_heuristic_refs_are_never_fact(client, acceptance_fixture_path):
    task_id = _task_with_mapping(client, acceptance_fixture_path)
    impact = client.get(f"/tasks/{task_id}/impact").json()
    for item in impact["config_refs"] + impact["db_refs"]:
        assert item["basis"] == "INFERENCE"


def test_impact_is_cached_and_deterministic(client, acceptance_fixture_path):
    task_id = _task_with_mapping(client, acceptance_fixture_path)
    first = client.get(f"/tasks/{task_id}/impact").json()
    second = client.get(f"/tasks/{task_id}/impact").json()
    refreshed = client.get(f"/tasks/{task_id}/impact?refresh=true").json()

    for key in (
        "changed_set",
        "blast_radius",
        "callers",
        "related_tests",
        "regression_areas",
        "risk_signal_bundle",
        "report",
    ):
        assert first[key] == second[key] == refreshed[key]


def test_impact_without_mapping_is_409(client, acceptance_fixture_path):
    repo_id = client.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)},
    ).json()["id"]
    snapshot_id = client.post(f"/repositories/{repo_id}/snapshots", json={}).json()[
        "snapshot_id"
    ]
    client.post(f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis", json={})
    task_md = (acceptance_fixture_path / "task.md").read_text(encoding="utf-8")
    task_id = client.post(
        "/tasks", json={"repository_id": repo_id, "text": task_md}
    ).json()["task"]["id"]

    r = client.get(f"/tasks/{task_id}/impact")
    assert r.status_code == 409
    assert r.json()["code"] == "IMPACT_MAPPING_MISSING"


def test_impact_unknown_task_is_404(client):
    r = client.get("/tasks/does-not-exist/impact")
    assert r.status_code == 404
    assert r.json()["code"] == "IMPACT_TASK_NOT_FOUND"
