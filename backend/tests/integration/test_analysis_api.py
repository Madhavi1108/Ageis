"""API-level round trip: ingest -> POST .../analysis -> GET .../analysis."""

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
    engine = create_engine(f"sqlite:///{tmp_path / 'api_test.db'}")
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


def test_analysis_round_trip(client, acceptance_fixture_path):
    create_resp = client.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)},
    )
    repo_id = create_resp.json()["id"]

    snapshot_resp = client.post(f"/repositories/{repo_id}/snapshots", json={})
    snapshot_id = snapshot_resp.json()["snapshot_id"]

    post_resp = client.post(
        f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis", json={}
    )
    assert post_resp.status_code == 201, post_resp.text
    body = post_resp.json()
    assert body["symbol_count"] == 7
    assert body["dependency_count"] == 1

    get_resp = client.get(f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis")
    assert get_resp.status_code == 200
    assert get_resp.json()["symbol_count"] == 7


def test_get_analysis_before_running_returns_404(client, acceptance_fixture_path):
    create_resp = client.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)},
    )
    repo_id = create_resp.json()["id"]
    snapshot_resp = client.post(f"/repositories/{repo_id}/snapshots", json={})
    snapshot_id = snapshot_resp.json()["snapshot_id"]

    resp = client.get(f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis")
    assert resp.status_code == 404
    assert resp.json()["code"] == "ANALYSIS_NOT_FOUND"


def test_analysis_on_unknown_snapshot_returns_404(client, acceptance_fixture_path):
    create_resp = client.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)},
    )
    repo_id = create_resp.json()["id"]

    resp = client.post(
        f"/repositories/{repo_id}/snapshots/does-not-exist/analysis", json={}
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "ANALYSIS_SNAPSHOT_NOT_FOUND"
