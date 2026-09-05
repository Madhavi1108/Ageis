"""API-level round trip: POST /repositories -> POST snapshots -> GET /repositories/{id}.

Mirrors test_app_health.py's TestClient style. Uses FastAPI's dependency_overrides
(rather than env vars) to point the app's DB session and Settings at test-scoped
values -- `app`/its DB engine are module-level singletons built once at import time
(see app/main.py, app/db/session.py), so overriding dependencies per-test is the
correct way to isolate these tests instead of relying on process env / cache_clear.
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


def test_repositories_round_trip(client, acceptance_fixture_path):
    create_resp = client.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)},
    )
    assert create_resp.status_code == 201, create_resp.text
    repo_body = create_resp.json()
    assert repo_body["name"] == "aegis-acceptance"

    snapshot_resp = client.post(f"/repositories/{repo_body['id']}/snapshots", json={})
    assert snapshot_resp.status_code == 201, snapshot_resp.text
    snapshot_body = snapshot_resp.json()
    assert snapshot_body["status"] == "READY"
    assert snapshot_body["file_count"] == 6

    get_resp = client.get(f"/repositories/{repo_body['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == repo_body["id"]


def test_get_unknown_repository_returns_404(client):
    resp = client.get("/repositories/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["code"] == "INGEST_NOT_FOUND"
