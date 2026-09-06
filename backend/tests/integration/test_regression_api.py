"""Phase 15 integration: regression classification over the acceptance fixture."""

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
_EDIT_OPS = {
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
_TESTS = {
    "test_cases": [
        {
            "name": "test_above_max",
            "path": "test_invoice_boundary.py",
            "target_symbol": "invoice.py::calculate_total",
            "kind": "BOUNDARY",
            "rationale": "cap",
            "code": "from invoice import calculate_total\n\n\ndef test_above_max():\n"
            "    assert calculate_total(100.0, 0.9) == 50.0\n",
            "evidence": [],
        }
    ]
}


@pytest.fixture
def client(tmp_path, acceptance_fixture_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'regression_test.db'}")
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


def _through_phase_11(client, provider, acceptance_fixture_path) -> str:
    repo_id = client.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)},
    ).json()["id"]
    sid = client.post(f"/repositories/{repo_id}/snapshots", json={}).json()[
        "snapshot_id"
    ]
    client.post(f"/repositories/{repo_id}/snapshots/{sid}/analysis", json={})
    task_md = (acceptance_fixture_path / "task.md").read_text(encoding="utf-8")
    task_id = client.post(
        "/tasks", json={"repository_id": repo_id, "text": task_md}
    ).json()["task"]["id"]
    client.post("/analysis/map", json={"task_id": task_id})
    client.get(f"/tasks/{task_id}/impact")
    provider.register("planning", task_id, _PLAN)
    client.post(f"/tasks/{task_id}/plan")
    client.post(f"/tasks/{task_id}/plan/validate")
    provider.register("implementation", task_id, _EDIT_OPS)
    client.post(f"/tasks/{task_id}/changes")
    provider.register("test_synthesis", task_id, _TESTS)
    client.post(f"/tasks/{task_id}/tests")
    return task_id


def test_classifies_and_selects(client, acceptance_fixture_path):
    c, provider = client
    task_id = _through_phase_11(c, provider, acceptance_fixture_path)

    r = c.get(f"/tasks/{task_id}/regression")
    assert r.status_code == 200, r.text
    body = r.json()
    plan = body["plan"]

    assert "invoice.py::calculate_total" in plan["changed_symbols"]

    by_id = {t["test_id"]: t for t in plan["tests"]}
    invoice_tests = [t for tid, t in by_id.items() if tid.startswith("test_invoice.py")]
    assert invoice_tests and all(
        t["classification"] == "TARGETED" for t in invoice_tests
    )
    assert all(t["rationale"] for t in plan["tests"])

    gen = next(t for tid, t in by_id.items() if "test_above_max" in tid)
    assert gen["classification"] == "TARGETED"

    assert plan["selection"]["repair"]
    assert body["executed"] is False
    assert c.get(f"/tasks/{task_id}").json()["state"] == "REGRESSION_TESTING"


def test_cache_and_refresh_and_full_mode(client, acceptance_fixture_path):
    c, provider = client
    task_id = _through_phase_11(c, provider, acceptance_fixture_path)

    first = c.get(f"/tasks/{task_id}/regression").json()
    second = c.get(f"/tasks/{task_id}/regression").json()
    assert first["plan"]["tests"] == second["plan"]["tests"]

    refreshed = c.get(f"/tasks/{task_id}/regression?refresh=true").json()
    assert refreshed["plan"]["tests"] == first["plan"]["tests"]

    full = c.get(f"/tasks/{task_id}/regression?mode=full").json()["plan"]
    assert set(full["selection"]["pre_verification"]) == {
        t["test_id"] for t in full["tests"]
    }
    assert full["mode"] == "full"


def test_execute_without_docker(client, acceptance_fixture_path):
    c, provider = client
    task_id = _through_phase_11(c, provider, acceptance_fixture_path)
    body = c.get(f"/tasks/{task_id}/regression?execute=true").json()
    assert body["executed"] is False
    assert "sandbox" in (body["reason"] or "").lower()


def test_without_impact_is_409(client, acceptance_fixture_path):
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

    r = c.get(f"/tasks/{task_id}/regression")
    assert r.status_code == 409
    assert r.json()["code"] == "REGRESSION_INPUTS_MISSING"


def test_unknown_task_is_404(client):
    c, _ = client
    r = c.get("/tasks/nope/regression")
    assert r.status_code == 404
    assert r.json()["code"] == "REGRESSION_TASK_NOT_FOUND"
