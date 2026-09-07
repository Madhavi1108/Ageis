"""Phase 19 integration: POST/GET /tasks/{id}/pr over HTTP (LOCAL repo, no
token -> a local PR-body artifact) plus the not-verified / not-found gates.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.deps import get_ai_provider
from app.ai.provider import MockProvider
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import app
from app.models.base import Base

_PLAN = {
    "problem_interpretation": "cap the discount rate at 0.5",
    "assumptions": [],
    "files_to_inspect": ["invoice.py"],
    "files_to_modify": ["invoice.py"],
    "symbols_to_modify": ["invoice.py::calculate_total"],
    "dependencies": [],
    "steps": [
        {"id": "s1", "description": "clamp", "test_intent": "90 == 50", "evidence_refs": []}
    ],
    "test_strategy": {"approach": "boundary"},
    "expected_behavior": "the discount never exceeds 0.5",
    "regression_risks": [],
    "rollback_strategy": "revert invoice.py",
    "source": "AI",
    "confidence": {"value": 0.8, "basis": "INFERENCE"},
    "evidence": [],
}
_EDIT = {
    "edit_ops": [
        {
            "path": "invoice.py",
            "op": "replace",
            "anchor": "return price * (1 - discount)",
            "new": "discount = min(discount, 0.5)\n    return price * (1 - discount)",
            "plan_step_id": "s1",
            "rationale": "cap",
            "evidence": [],
        }
    ]
}


@pytest.fixture
def client(tmp_path, acceptance_fixture_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'pr_test.db'}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    provider = MockProvider()

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
    app.dependency_overrides[get_ai_provider] = lambda: provider
    try:
        with TestClient(app) as c:
            yield c, provider, acceptance_fixture_path
    finally:
        app.dependency_overrides.clear()


def _through_changes(c, provider, fixture) -> str:
    repo_id = c.post(
        "/repositories", json={"source_type": "LOCAL", "url_or_path": str(fixture)}
    ).json()["id"]
    sid = c.post(f"/repositories/{repo_id}/snapshots", json={}).json()["snapshot_id"]
    c.post(f"/repositories/{repo_id}/snapshots/{sid}/analysis", json={})
    task_md = (fixture / "task.md").read_text(encoding="utf-8")
    task_id = c.post("/tasks", json={"repository_id": repo_id, "text": task_md}).json()[
        "task"
    ]["id"]
    c.post("/analysis/map", json={"task_id": task_id})
    c.get(f"/tasks/{task_id}/impact")
    provider.register("planning", task_id, _PLAN)
    c.post(f"/tasks/{task_id}/plan")
    c.post(f"/tasks/{task_id}/plan/validate")
    provider.register("implementation", task_id, _EDIT)
    assert c.post(f"/tasks/{task_id}/changes").status_code == 201
    return task_id


def _through_verified(c, provider, fixture) -> str:
    task_id = _through_changes(c, provider, fixture)
    c.get(f"/tasks/{task_id}/verification")
    # no Docker in CI -> PARTIAL -> a human APPROVE lands it at VERIFIED
    r = c.post(
        f"/tasks/{task_id}/verification/decision",
        json={"decision": "APPROVE", "reason": "manually validated", "actor": "u@x"},
    )
    assert r.status_code == 200 and r.json()["verdict"] == "VERIFIED"
    return task_id


def test_pr_local_artifact_when_no_token(client):
    c, provider, fixture = client
    task_id = _through_verified(c, provider, fixture)

    r = c.post(f"/tasks/{task_id}/pr", json={})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["mode"] == "LOCAL_ARTIFACT"
    assert body["state"] == "DRAFTED"
    assert body["github_url"] is None
    assert body["body_artifact_id"]

    got = c.get(f"/tasks/{task_id}/pr")
    assert got.status_code == 200
    assert got.json()["id"] == body["id"]


def test_pr_requires_verified_task(client):
    c, provider, fixture = client
    task_id = _through_changes(c, provider, fixture)  # stops before verification

    r = c.post(f"/tasks/{task_id}/pr", json={})
    assert r.status_code == 409
    assert r.json()["code"] == "PR_NOT_VERIFIED"


def test_pr_unknown_task_is_404(client):
    c, _, _ = client
    assert c.post("/tasks/nope/pr", json={}).status_code == 404
    assert c.get("/tasks/nope/pr").status_code == 404


def test_get_pr_before_creation_is_404(client):
    c, provider, fixture = client
    task_id = _through_verified(c, provider, fixture)
    r = c.get(f"/tasks/{task_id}/pr")
    assert r.status_code == 404
    assert r.json()["code"] == "PR_NOT_FOUND"
