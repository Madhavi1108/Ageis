"""Phase 27 integration: /readyz readiness probe + /metrics snapshot."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import circuit_breaker
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import app
from app.models.base import Base


@pytest.fixture
def client(tmp_path, acceptance_fixture_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'health_test.db'}")
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
    circuit_breaker.reset_all()
    try:
        with TestClient(app) as c:
            yield c, acceptance_fixture_path
    finally:
        app.dependency_overrides.clear()
        circuit_breaker.reset_all()


def test_readyz_ok_when_db_reachable(client):
    c, _ = client
    r = c.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


def test_metrics_reports_queue_depth_jobs_and_breakers(client):
    c, fixture = client
    repo_id = c.post(
        "/repositories", json={"source_type": "LOCAL", "url_or_path": str(fixture)}
    ).json()["id"]
    task_md = (fixture / "task.md").read_text(encoding="utf-8")
    task_id = c.post("/tasks", json={"repository_id": repo_id, "text": task_md}).json()[
        "task"
    ]["id"]
    c.post(f"/tasks/{task_id}/run")  # one QUEUED RUN_TASK job

    body = c.get("/metrics").json()
    assert body["queue_depth"] >= 1
    assert body["jobs"]["QUEUED"] >= 1
    assert isinstance(body["circuit_breakers"], list)


def test_metrics_shows_open_circuit_breaker(client):
    c, _ = client
    cb = circuit_breaker.get_breaker("wiring-test", fail_threshold=1, reset_after_s=60.0)
    try:
        cb.call(_boom)
    except RuntimeError:
        pass
    rows = {row["name"]: row for row in c.get("/metrics").json()["circuit_breakers"]}
    assert rows["wiring-test"]["state"] == "OPEN"


def _boom() -> None:
    raise RuntimeError("down")
