"""Phase 16 integration: code review of the latest patch."""

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
        {
            "id": "s1",
            "description": "clamp",
            "test_intent": "90% == 50%",
            "evidence_refs": [],
        }
    ],
    "test_strategy": {"approach": "boundary"},
    "expected_behavior": "capped",
    "regression_risks": [],
    "rollback_strategy": "revert invoice.py",
    "source": "AI",
    "confidence": {"value": 0.8, "basis": "INFERENCE"},
    "evidence": [],
}
_CLEAN_EDIT = {
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
_SHELL_EDIT = {
    "edit_ops": [
        {
            "path": "invoice.py",
            "op": "replace",
            "anchor": "return price * (1 - discount)",
            "new": "import subprocess\n"
            "    subprocess.run('echo hi', shell=True)\n"
            "    return price * (1 - discount)",
            "plan_step_id": "s1",
            "rationale": "oops",
            "evidence": [],
        }
    ]
}


@pytest.fixture
def client(tmp_path, acceptance_fixture_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'review_test.db'}")
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
            yield c, provider
    finally:
        app.dependency_overrides.clear()


def _through_changes(c, provider, acceptance_fixture_path, edit_ops) -> str:
    repo_id = c.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)},
    ).json()["id"]
    sid = c.post(f"/repositories/{repo_id}/snapshots", json={}).json()["snapshot_id"]
    c.post(f"/repositories/{repo_id}/snapshots/{sid}/analysis", json={})
    task_md = (acceptance_fixture_path / "task.md").read_text(encoding="utf-8")
    task_id = c.post("/tasks", json={"repository_id": repo_id, "text": task_md}).json()[
        "task"
    ]["id"]
    c.post("/analysis/map", json={"task_id": task_id})
    c.get(f"/tasks/{task_id}/impact")
    provider.register("planning", task_id, _PLAN)
    c.post(f"/tasks/{task_id}/plan")
    c.post(f"/tasks/{task_id}/plan/validate")
    provider.register("implementation", task_id, edit_ops)
    r = c.post(f"/tasks/{task_id}/changes")
    assert r.status_code == 201, r.text
    return task_id


def test_clean_patch_review(client, acceptance_fixture_path):
    c, provider = client
    task_id = _through_changes(c, provider, acceptance_fixture_path, _CLEAN_EDIT)

    r = c.get(f"/tasks/{task_id}/review")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["implementation_version"] == 1
    assert body["blocking"] is False
    assert not any(f["severity"] == "CRITICAL" for f in body["findings"])
    assert "ruff" in body["static_tools_run"]
    assert c.get(f"/tasks/{task_id}").json()["state"] == "REVIEWING"

    second = c.get(f"/tasks/{task_id}/review").json()
    assert second["findings"] == body["findings"]
    refreshed = c.get(f"/tasks/{task_id}/review?refresh=true").json()
    assert refreshed["findings"] == body["findings"]


def test_shell_true_patch_is_blocking(client, acceptance_fixture_path):
    c, provider = client
    task_id = _through_changes(c, provider, acceptance_fixture_path, _SHELL_EDIT)

    body = c.get(f"/tasks/{task_id}/review").json()
    sec = [
        f
        for f in body["findings"]
        if f["category"] == "SECURITY" and f["severity"] == "HIGH"
    ]
    assert sec, body["findings"]
    hit = sec[0]
    assert hit["file"] == "invoice.py"
    assert hit["line_start"]
    assert hit["recommendation"]
    assert body["blocking"] is True


def test_review_without_implementation_is_409(client, acceptance_fixture_path):
    c, _ = client
    repo_id = c.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)},
    ).json()["id"]
    sid = c.post(f"/repositories/{repo_id}/snapshots", json={}).json()["snapshot_id"]
    c.post(f"/repositories/{repo_id}/snapshots/{sid}/analysis", json={})
    task_md = (acceptance_fixture_path / "task.md").read_text(encoding="utf-8")
    task_id = c.post("/tasks", json={"repository_id": repo_id, "text": task_md}).json()[
        "task"
    ]["id"]

    r = c.get(f"/tasks/{task_id}/review")
    assert r.status_code == 409
    assert r.json()["code"] == "REVIEW_IMPLEMENTATION_MISSING"


def test_unknown_task_is_404(client):
    c, _ = client
    r = c.get("/tasks/nope/review")
    assert r.status_code == 404
    assert r.json()["code"] == "REVIEW_TASK_NOT_FOUND"
