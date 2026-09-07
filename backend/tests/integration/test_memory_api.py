"""Phase 20 integration: GET /memory, POST /memory/search, GET /tasks/{id}/memory."""

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
    engine = create_engine(f"sqlite:///{tmp_path / 'memory_test.db'}")
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
            memory_enabled=True,
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


def _through_verified(c, provider, fixture) -> tuple[str, str]:
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
    c.get(f"/tasks/{task_id}/verification")
    r = c.post(
        f"/tasks/{task_id}/verification/decision",
        json={"decision": "APPROVE", "reason": "ok", "actor": "u@x"},
    )
    assert r.status_code == 200 and r.json()["verdict"] == "VERIFIED"
    return task_id, repo_id


def test_memory_record_written_and_served(client):
    c, provider, fixture = client
    task_id, repo_id = _through_verified(c, provider, fixture)

    got = c.get(f"/tasks/{task_id}/memory")
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["task_id"] == task_id
    assert body["outcome"] == "VERIFIED"
    assert "invoice.py" in body["touched_files"]
    assert body["fix_summary"]

    listed = c.get("/memory", params={"repository_id": repo_id}).json()
    assert [m["task_id"] for m in listed] == [task_id]


def test_memory_search_is_ranked_and_deterministic(client):
    c, provider, fixture = client
    task_id, repo_id = _through_verified(c, provider, fixture)

    payload = {"query": "invoice discount cap calculate_total", "repository_id": repo_id}
    first = c.post("/memory/search", json=payload)
    assert first.status_code == 200, first.text
    hits = first.json()
    assert hits and hits[0]["task_id"] == task_id
    assert hits[0]["similarity"] > 0
    assert hits[0]["same_repository"] is True
    assert hits[0]["provenance"].startswith(f"task {task_id} (VERIFIED,")
    assert "verify" in hits[0]["label"].lower()

    assert c.post("/memory/search", json=payload).json() == hits  # deterministic


def test_memory_404s(client):
    c, provider, fixture = client
    # a task with no terminal state yet
    repo_id = c.post(
        "/repositories", json={"source_type": "LOCAL", "url_or_path": str(fixture)}
    ).json()["id"]
    c.post(f"/repositories/{repo_id}/snapshots", json={})
    task_md = (fixture / "task.md").read_text(encoding="utf-8")
    task_id = c.post("/tasks", json={"repository_id": repo_id, "text": task_md}).json()[
        "task"
    ]["id"]

    r1 = c.get(f"/tasks/{task_id}/memory")
    assert r1.status_code == 404 and r1.json()["code"] == "MEMORY_NOT_FOUND"

    r2 = c.get("/tasks/nope/memory")
    assert r2.status_code == 404 and r2.json()["code"] == "MEMORY_TASK_NOT_FOUND"


def test_search_empty_when_no_memory(client):
    c, _, _ = client
    r = c.post("/memory/search", json={"query": "anything at all"})
    assert r.status_code == 200
    assert r.json() == []
