"""Phase 27 integration: POST /tasks/{id}/run returns 429 when the job queue
is at its configured depth (admission control / backpressure)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import app
from app.models.base import Base

_MAX_DEPTH = 3


@pytest.fixture
def client(tmp_path, acceptance_fixture_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'bp_test.db'}")
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
            job_max_queue_depth=_MAX_DEPTH,
            _env_file=None,
        )

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_settings] = _get_settings
    try:
        with TestClient(app) as c:
            yield c, acceptance_fixture_path
    finally:
        app.dependency_overrides.clear()


def test_run_is_rejected_with_429_once_the_queue_is_full(client):
    c, fixture = client
    repo_id = c.post(
        "/repositories", json={"source_type": "LOCAL", "url_or_path": str(fixture)}
    ).json()["id"]
    task_md = (fixture / "task.md").read_text(encoding="utf-8")

    task_ids = []
    for i in range(_MAX_DEPTH):
        tid = c.post(
            "/tasks",
            json={"repository_id": repo_id, "text": f"{task_md}\n\nvariant {i}"},
        ).json()["task"]["id"]
        assert c.post(f"/tasks/{tid}/run").status_code == 200
        task_ids.append(tid)

    overflow = c.post(
        "/tasks", json={"repository_id": repo_id, "text": f"{task_md}\n\noverflow"}
    ).json()["task"]["id"]
    r = c.post(f"/tasks/{overflow}/run")
    assert r.status_code == 429
    body = r.json()
    assert body["code"] == "JOB_QUEUE_FULL"
    assert body["details"]["queue_depth"] == _MAX_DEPTH
    assert body["details"]["limit"] == _MAX_DEPTH
    assert task_ids  # the first _MAX_DEPTH runs were all admitted
