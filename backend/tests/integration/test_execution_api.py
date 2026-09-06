"""Phase 12 integration: EXECUTING_TESTS over the acceptance fixture -- full
pipeline through generated tests, then POST/GET /tasks/{id}/executions and
GET /executions/{id}. Docker is unavailable in this dev environment, so the
real run degrades to PARTIALLY_SUPPORTED (proving the "no host fallback"
contract) -- see docs/AEGIS_IMPLEMENTATION_PLAN.md Section 20.
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
    "problem_interpretation": "cap the discount rate at 0.5 in calculate_total",
    "assumptions": [],
    "files_to_inspect": ["invoice.py"],
    "files_to_modify": ["invoice.py"],
    "symbols_to_modify": ["invoice.py::calculate_total"],
    "dependencies": [],
    "steps": [
        {
            "id": "s1",
            "description": "clamp discount to 0.5 before applying it",
            "test_intent": "a 90% discount behaves like a 50% discount",
            "evidence_refs": [],
        }
    ],
    "test_strategy": {"approach": "add a boundary test at discount=0.9"},
    "expected_behavior": "calculate_total(100, 0.9) == 50.0",
    "regression_risks": [],
    "rollback_strategy": "revert invoice.py to the snapshot version",
    "source": "AI",
    "confidence": {"value": 0.82, "basis": "INFERENCE"},
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
            "rationale": "cap discount at 0.5 before applying it",
            "evidence": [],
        }
    ]
}

_TEST_CASES = {
    "test_cases": [
        {
            "name": "test_discount_at_max",
            "path": "test_invoice_boundary.py",
            "target_symbol": "invoice.py::calculate_total",
            "kind": "BOUNDARY",
            "rationale": "discount exactly at the cap",
            "code": (
                "from invoice import calculate_total\n\n\n"
                "def test_discount_at_max():\n"
                "    assert calculate_total(100.0, 0.5) == 50.0\n"
            ),
            "evidence": [],
        },
        {
            "name": "test_discount_above_max",
            "path": "test_invoice_negative.py",
            "target_symbol": "invoice.py::calculate_total",
            "kind": "NEGATIVE",
            "rationale": "a discount above the cap must still be capped",
            "code": (
                "from invoice import calculate_total\n\n\n"
                "def test_discount_above_max():\n"
                "    assert calculate_total(100.0, 0.9) == 50.0\n"
            ),
            "evidence": [],
        },
    ]
}


@pytest.fixture
def ctx(tmp_path, acceptance_fixture_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'execution_test.db'}")
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
        with TestClient(app) as client:
            yield client, provider
    finally:
        app.dependency_overrides.clear()


def _prepare_tested_task(client, provider, acceptance_fixture_path) -> str:
    repo_id = client.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)},
    ).json()["id"]
    snapshot_id = client.post(f"/repositories/{repo_id}/snapshots", json={}).json()[
        "snapshot_id"
    ]
    client.post(f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis", json={})
    task_md = (acceptance_fixture_path / "task.md").read_text(encoding="utf-8")
    task_id = client.post(
        "/tasks", json={"repository_id": repo_id, "text": task_md}
    ).json()["task"]["id"]
    assert client.post("/analysis/map", json={"task_id": task_id}).status_code == 201
    assert client.get(f"/tasks/{task_id}/impact").status_code == 200

    provider.register("planning", task_id, _PLAN)
    assert client.post(f"/tasks/{task_id}/plan").status_code == 201
    val = client.post(f"/tasks/{task_id}/plan/validate").json()
    assert val["validation"]["verdict"] == "APPROVED", val

    provider.register("implementation", task_id, _EDIT_OPS)
    assert client.post(f"/tasks/{task_id}/changes").status_code == 201

    provider.register("test_synthesis", task_id, _TEST_CASES)
    assert client.post(f"/tasks/{task_id}/tests").status_code == 201

    return task_id


def test_execute_tests_without_docker_is_partially_supported(
    ctx, acceptance_fixture_path
):
    """This dev environment has no Docker daemon -- the real, documented
    behaviour (ADR-0010: no host fallback) is exercised end to end."""
    client, provider = ctx
    task_id = _prepare_tested_task(client, provider, acceptance_fixture_path)

    gen = client.post(f"/tasks/{task_id}/executions")
    assert gen.status_code == 201, gen.text
    body = gen.json()
    assert body["outcome"] == "PARTIALLY_SUPPORTED"
    assert "docker" in body["reason"].lower()
    assert body["version"] == 1
    assert "test_invoice_boundary.py" in body["command"]
    assert "test_invoice_negative.py" in body["command"]

    got = client.get(f"/executions/{body['id']}")
    assert got.status_code == 200
    assert got.json()["outcome"] == "PARTIALLY_SUPPORTED"

    listing = client.get(f"/tasks/{task_id}/executions").json()
    assert len(listing) == 1
    assert listing[0]["version"] == 1

    assert client.get(f"/tasks/{task_id}").json()["state"] == "EXECUTING_TESTS"


def test_execute_without_generated_tests_is_409(ctx, acceptance_fixture_path):
    client, provider = ctx
    repo_id = client.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)},
    ).json()["id"]
    snapshot_id = client.post(f"/repositories/{repo_id}/snapshots", json={}).json()[
        "snapshot_id"
    ]
    client.post(f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis", json={})
    task_md = (acceptance_fixture_path / "task.md").read_text(encoding="utf-8")
    task_id = client.post(
        "/tasks", json={"repository_id": repo_id, "text": task_md}
    ).json()["task"]["id"]

    r = client.post(f"/tasks/{task_id}/executions")
    assert r.status_code == 409
    assert r.json()["code"] == "TEST_EXECUTION_TESTS_MISSING"


def test_get_execution_404(ctx, acceptance_fixture_path):
    client, _ = ctx
    r = client.get("/executions/does-not-exist")
    assert r.status_code == 404
    assert r.json()["code"] == "TEST_EXECUTION_NOT_FOUND"


def test_reexecute_versions(ctx, acceptance_fixture_path):
    client, provider = ctx
    task_id = _prepare_tested_task(client, provider, acceptance_fixture_path)
    first = client.post(f"/tasks/{task_id}/executions").json()
    second = client.post(f"/tasks/{task_id}/executions").json()
    assert first["version"] == 1
    assert second["version"] == 2
