"""Phase 7 integration: map the real aegis-acceptance fixture end to end.

See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 15 "Phase-wise testing".
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
    engine = create_engine(f"sqlite:///{tmp_path / 'mapping_test.db'}")
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


def _ingest_analyze(client, acceptance_fixture_path) -> str:
    repo_id = client.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)},
    ).json()["id"]
    snapshot_id = client.post(f"/repositories/{repo_id}/snapshots", json={}).json()[
        "snapshot_id"
    ]
    r = client.post(
        f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis", json={}
    )
    assert r.status_code == 201, r.text
    return repo_id


def _create_task(client, repo_id, acceptance_fixture_path) -> str:
    task_md = (acceptance_fixture_path / "task.md").read_text(encoding="utf-8")
    r = client.post("/tasks", json={"repository_id": repo_id, "text": task_md})
    assert r.status_code == 201, r.text
    return r.json()["task"]["id"]


def test_map_task_localizes_invoice_calculate_total(client, acceptance_fixture_path):
    repo_id = _ingest_analyze(client, acceptance_fixture_path)
    task_id = _create_task(client, repo_id, acceptance_fixture_path)

    r = client.post("/analysis/map", json={"task_id": task_id})
    assert r.status_code == 201, r.text
    mapping = r.json()

    paths = [c["path"] for c in mapping["candidates"]]
    assert "invoice.py" in paths
    # invoice.py should be the top candidate for this issue
    assert paths[0] == "invoice.py"

    invoice = next(c for c in mapping["candidates"] if c["path"] == "invoice.py")
    assert "calculate_total" in invoice["symbols"]
    assert invoice["evidence"], "candidate must carry evidence"
    assert "FACT" in invoice["labels"]

    # every candidate obeys the no-evidence-free rule + has a confidence
    for c in mapping["candidates"]:
        assert len(c["evidence"]) >= 1
        assert 0.0 <= c["confidence"] <= 1.0

    assert 0.0 < mapping["overall_confidence"] <= 1.0
    assert mapping["semantic_available"] is False
    assert mapping["model_version"] == "mapping-model v1.0.0"
    assert "test_invoice.py" in mapping["related_tests"]


def test_snapshot_is_bound_to_the_task(client, acceptance_fixture_path):
    repo_id = _ingest_analyze(client, acceptance_fixture_path)
    task_id = _create_task(client, repo_id, acceptance_fixture_path)
    assert client.get(f"/tasks/{task_id}").json()["snapshot_id"] is None

    client.post("/analysis/map", json={"task_id": task_id})
    assert client.get(f"/tasks/{task_id}").json()["snapshot_id"] is not None


def test_get_mapping_returns_persisted_document(client, acceptance_fixture_path):
    repo_id = _ingest_analyze(client, acceptance_fixture_path)
    task_id = _create_task(client, repo_id, acceptance_fixture_path)

    posted = client.post("/analysis/map", json={"task_id": task_id}).json()
    got = client.get(f"/tasks/{task_id}/mapping")
    assert got.status_code == 200
    assert got.json()["candidates"] == posted["candidates"]
    assert got.json()["task_id"] == task_id


def test_get_mapping_404_before_compute(client, acceptance_fixture_path):
    repo_id = _ingest_analyze(client, acceptance_fixture_path)
    task_id = _create_task(client, repo_id, acceptance_fixture_path)
    r = client.get(f"/tasks/{task_id}/mapping")
    assert r.status_code == 404
    assert r.json()["code"] == "MAPPING_NOT_FOUND"


def test_map_is_deterministic(client, acceptance_fixture_path):
    repo_id = _ingest_analyze(client, acceptance_fixture_path)
    task_id = _create_task(client, repo_id, acceptance_fixture_path)

    first = client.post("/analysis/map", json={"task_id": task_id}).json()
    second = client.post("/analysis/map", json={"task_id": task_id}).json()
    assert first["candidates"] == second["candidates"]
    assert first["overall_confidence"] == second["overall_confidence"]
    assert first["related_tests"] == second["related_tests"]


def test_map_without_analysis_is_409(client, acceptance_fixture_path):
    repo_id = client.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)},
    ).json()["id"]
    client.post(f"/repositories/{repo_id}/snapshots", json={})
    task_md = (acceptance_fixture_path / "task.md").read_text(encoding="utf-8")
    task_id = client.post(
        "/tasks", json={"repository_id": repo_id, "text": task_md}
    ).json()["task"]["id"]

    r = client.post("/analysis/map", json={"task_id": task_id})
    assert r.status_code == 409
    assert r.json()["code"] == "MAPPING_SNAPSHOT_NOT_READY"


def test_stateless_map_needs_both_snapshot_and_text(client, acceptance_fixture_path):
    r = client.post("/analysis/map", json={"snapshot_id": "abc"})
    assert r.status_code == 422
