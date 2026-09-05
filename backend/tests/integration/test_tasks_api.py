"""API round trip for the six /tasks routes. See docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 14 "Phase-wise testing" Integration bullet. Mirrors test_graph_api.py's
client fixture.
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
    engine = create_engine(f"sqlite:///{tmp_path / 'tasks_api_test.db'}")
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


@pytest.fixture
def repo_id(client, acceptance_fixture_path):
    resp = client.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_create_persists_and_returns(client, repo_id):
    resp = client.post(
        "/tasks",
        json={
            "repository_id": repo_id,
            "text": "Fix incorrect invoice total when the discount exceeds the max",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["task"]["state"] == "PENDING"
    assert body["task"]["task_type"] == "BUG"
    assert body["task"]["title"].startswith("Fix incorrect invoice total")
    assert body["normalization"] == {
        "truncated": False,
        "original_bytes": len(
            "Fix incorrect invoice total when the discount exceeds the max".encode()
        ),
        "stored_bytes": len(
            "Fix incorrect invoice total when the discount exceeds the max".encode()
        ),
    }

    got = client.get(f"/tasks/{body['task']['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == body["task"]["id"]


def test_get_unknown_task_returns_404(client):
    resp = client.get("/tasks/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["code"] == "TASK_NOT_FOUND"


def test_duplicate_post_returns_409_with_existing_id(client, repo_id):
    payload = {"repository_id": repo_id, "text": "Add a CSV export button"}
    first = client.post("/tasks", json=payload)
    assert first.status_code == 201
    dup = client.post("/tasks", json=payload)
    assert dup.status_code == 409
    assert dup.json()["code"] == "TASK_DUPLICATE"
    assert dup.json()["details"]["existing_task_id"] == first.json()["task"]["id"]


def test_run_enqueues_a_job_and_sets_queued(client, repo_id):
    task_id = client.post(
        "/tasks", json={"repository_id": repo_id, "text": "Implement pagination"}
    ).json()["task"]["id"]

    resp = client.post(f"/tasks/{task_id}/run")
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] == "QUEUED"

    timeline = client.get(f"/tasks/{task_id}/timeline").json()
    job_events = [e for e in timeline["entries"] if e["kind"] == "JOB"]
    assert any(e["state"] == "JOB_QUEUED" for e in job_events)


def test_run_twice_is_rejected(client, repo_id):
    task_id = client.post(
        "/tasks", json={"repository_id": repo_id, "text": "Add retry with backoff"}
    ).json()["task"]["id"]
    assert client.post(f"/tasks/{task_id}/run").status_code == 200
    again = client.post(f"/tasks/{task_id}/run")
    assert again.status_code == 409
    assert again.json()["code"] == "TASK_INVALID_STATE"
    assert again.json()["details"]["current_state"] == "QUEUED"


def test_cancel_sets_cancelled_and_halts_progression(client, repo_id):
    task_id = client.post(
        "/tasks", json={"repository_id": repo_id, "text": "Support webhooks"}
    ).json()["task"]["id"]

    resp = client.post(f"/tasks/{task_id}/cancel", json={"reason": "descoped"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] == "CANCELLED"
    assert resp.json()["terminal_reason"] == "descoped"

    # A cancelled task cannot be run.
    assert client.post(f"/tasks/{task_id}/run").status_code == 409


def test_cancel_after_run_cancels_the_job(client, repo_id):
    task_id = client.post(
        "/tasks", json={"repository_id": repo_id, "text": "Add dark mode"}
    ).json()["task"]["id"]
    client.post(f"/tasks/{task_id}/run")

    assert client.post(f"/tasks/{task_id}/cancel").json()["state"] == "CANCELLED"

    timeline = client.get(f"/tasks/{task_id}/timeline").json()
    job_states = [e["state"] for e in timeline["entries"] if e["kind"] == "JOB"]
    assert "JOB_CANCELLED" in job_states


def test_timeline_reflects_steps_in_order(client, repo_id):
    task_id = client.post(
        "/tasks", json={"repository_id": repo_id, "text": "Add a health metric"}
    ).json()["task"]["id"]
    client.post(f"/tasks/{task_id}/run")

    entries = client.get(f"/tasks/{task_id}/timeline").json()["entries"]
    step_states = [e["state"] for e in entries if e["kind"] == "STEP"]
    assert step_states == ["PENDING", "QUEUED"]
    # non-decreasing timestamps
    times = [e["at"] for e in entries]
    assert times == sorted(times)


def test_list_filters_by_repository_and_state(client, repo_id):
    a = client.post(
        "/tasks", json={"repository_id": repo_id, "text": "First task text"}
    ).json()["task"]["id"]
    client.post(
        "/tasks", json={"repository_id": repo_id, "text": "Second task text"}
    )
    client.post(f"/tasks/{a}/run")

    all_for_repo = client.get("/tasks", params={"repository_id": repo_id}).json()
    assert all_for_repo["total"] == 2
    assert len(all_for_repo["items"]) == 2

    queued = client.get(
        "/tasks", params={"repository_id": repo_id, "state": "QUEUED"}
    ).json()
    assert queued["total"] == 1
    assert queued["items"][0]["id"] == a


def test_create_with_structured_issue_links_an_issue_row(client, repo_id):
    resp = client.post(
        "/tasks",
        json={
            "repository_id": repo_id,
            "issue": {
                "source": "GITHUB",
                "external_ref": "123",
                "title": "Refactor the invoice module",
                "body": "Rename calculate_total to compute_total across the codebase.",
            },
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["task"]["issue_id"] is not None
    assert body["task"]["task_type"] == "REFACTOR"


def test_create_requires_exactly_one_body(client, repo_id):
    neither = client.post("/tasks", json={"repository_id": repo_id})
    assert neither.status_code == 422
    assert neither.json()["code"] == "TASK_INVALID_INPUT"
    both = client.post(
        "/tasks",
        json={
            "repository_id": repo_id,
            "text": "x",
            "issue": {"title": "t", "body": "b"},
        },
    )
    assert both.status_code == 422
    assert both.json()["code"] == "TASK_INVALID_INPUT"


def test_create_against_unknown_repository_404s(client):
    resp = client.post(
        "/tasks", json={"repository_id": "nope", "text": "some work"}
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "TASK_REPO_NOT_FOUND"
