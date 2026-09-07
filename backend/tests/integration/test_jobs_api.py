"""Phase 21 integration: the /jobs router."""

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
    engine = create_engine(f"sqlite:///{tmp_path / 'jobs_test.db'}")
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
            yield c, acceptance_fixture_path
    finally:
        app.dependency_overrides.clear()


def _task_with_job(c, fixture) -> tuple[str, str]:
    repo_id = c.post(
        "/repositories", json={"source_type": "LOCAL", "url_or_path": str(fixture)}
    ).json()["id"]
    task_md = (fixture / "task.md").read_text(encoding="utf-8")
    task_id = c.post("/tasks", json={"repository_id": repo_id, "text": task_md}).json()[
        "task"
    ]["id"]
    c.post(f"/tasks/{task_id}/run")  # enqueues a RUN_TASK job, task -> QUEUED
    jobs = c.get("/jobs", params={"task_id": task_id}).json()["items"]
    return task_id, jobs[0]["id"]


def test_list_and_get_job(client):
    c, fixture = client
    task_id, job_id = _task_with_job(c, fixture)

    listed = c.get("/jobs", params={"task_id": task_id})
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1 and body["limit"] == 50 and body["offset"] == 0
    assert body["items"][0]["type"] == "RUN_TASK"
    assert body["items"][0]["state"] == "QUEUED"

    one = c.get(f"/jobs/{job_id}")
    assert one.status_code == 200 and one.json()["id"] == job_id

    assert c.get("/jobs/nope").status_code == 404


def test_filter_by_state_and_type(client):
    c, fixture = client
    _task_with_job(c, fixture)
    assert c.get("/jobs", params={"state": "QUEUED"}).json()["total"] >= 1
    assert c.get("/jobs", params={"state": "SUCCEEDED"}).json()["total"] == 0
    assert c.get("/jobs", params={"type": "RUN_TASK"}).json()["total"] >= 1


def test_pagination(client):
    c, fixture = client
    repo_id = c.post(
        "/repositories", json={"source_type": "LOCAL", "url_or_path": str(fixture)}
    ).json()["id"]
    task_md = (fixture / "task.md").read_text(encoding="utf-8")
    for i in range(3):
        tid = c.post(
            "/tasks",
            json={"repository_id": repo_id, "text": f"{task_md}\nvariant {i}"},
        ).json()["task"]["id"]
        c.post(f"/tasks/{tid}/run")

    page1 = c.get("/jobs", params={"limit": 2, "offset": 0}).json()
    page2 = c.get("/jobs", params={"limit": 2, "offset": 2}).json()
    assert page1["total"] == 3
    assert len(page1["items"]) == 2 and len(page2["items"]) == 1
    assert {j["id"] for j in page1["items"]}.isdisjoint({j["id"] for j in page2["items"]})


def test_cancel_run_task_job_cancels_the_task(client):
    c, fixture = client
    task_id, job_id = _task_with_job(c, fixture)

    r = c.post(f"/jobs/{job_id}/cancel")
    assert r.status_code == 200, r.text
    assert c.get(f"/tasks/{task_id}").json()["state"] == "CANCELLED"

    # already-inactive job -> 409
    assert c.post(f"/jobs/{job_id}/cancel").status_code == 409
