"""Phase 9 integration: PLANNING -> PLAN_VALIDATION over the acceptance fixture.

See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 17 "Phase-wise testing".
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


def _canned_plan(files, symbols, *, source="AI"):
    return {
        "problem_interpretation": "cap the discount rate at 0.5 in calculate_total",
        "assumptions": ["the discount argument is a fraction in [0, 1]"],
        "files_to_inspect": list(files),
        "files_to_modify": list(files),
        "symbols_to_modify": list(symbols),
        "dependencies": [],
        "steps": [
            {
                "id": "s1",
                "description": "clamp discount to 0.5 before applying it",
                "test_intent": "a 90% discount behaves like a 50% discount",
                "evidence_refs": ["invoice.py::calculate_total"],
            }
        ],
        "test_strategy": {"approach": "add a boundary test at discount=0.9"},
        "expected_behavior": "calculate_total(100, 0.9) == 50.0",
        "regression_risks": ["existing no-discount path must still return price"],
        "rollback_strategy": "revert invoice.py to the snapshot version",
        "source": source,
        "confidence": {"value": 0.82, "basis": "INFERENCE"},
        "evidence": [
            {"kind": "symbol", "ref": "invoice.py::calculate_total", "detail": "target"}
        ],
    }


@pytest.fixture
def ctx(tmp_path, acceptance_fixture_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'planning_test.db'}")
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


def _prepare_task(client, acceptance_fixture_path) -> str:
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
    return task_id


def test_generate_then_validate_approves(ctx, acceptance_fixture_path):
    client, provider = ctx
    task_id = _prepare_task(client, acceptance_fixture_path)
    provider.register(
        "planning",
        task_id,
        _canned_plan(["invoice.py"], ["invoice.py::calculate_total"]),
    )

    gen = client.post(f"/tasks/{task_id}/plan")
    assert gen.status_code == 201, gen.text
    plan = gen.json()
    assert plan["version"] == 1
    assert plan["source"] == "AI"
    assert plan["files_to_modify"] == ["invoice.py"]
    assert plan["steps"][0]["test_intent"]
    assert plan["validation"] is None

    got = client.get(f"/tasks/{task_id}/plan")
    assert got.json()["version"] == 1

    val = client.post(f"/tasks/{task_id}/plan/validate")
    assert val.status_code == 200, val.text
    assert val.json()["validation"]["verdict"] == "APPROVED"
    assert set(val.json()["validation"]["checked"]) >= {
        "schema",
        "files_exist",
        "scope_subset",
        "steps_have_tests",
        "rollback_present",
    }

    assert client.get(f"/tasks/{task_id}").json()["state"] == "PLAN_VALIDATION"


def test_scope_escaping_plan_is_rejected(ctx, acceptance_fixture_path):
    client, provider = ctx
    task_id = _prepare_task(client, acceptance_fixture_path)
    provider.register(
        "planning",
        task_id,
        _canned_plan(["invoice.py", "totally_unrelated.py"], []),
    )
    client.post(f"/tasks/{task_id}/plan")
    val = client.post(f"/tasks/{task_id}/plan/validate").json()
    assert val["validation"]["verdict"] == "REJECTED"
    assert any(
        "scope" in r or "not in the snapshot" in r for r in val["validation"]["reasons"]
    )


def test_plan_before_inputs_is_409(ctx, acceptance_fixture_path):
    client, _ = ctx
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

    r = client.post(f"/tasks/{task_id}/plan")
    assert r.status_code == 409
    assert r.json()["code"] == "PLAN_INPUTS_MISSING"


def test_regenerate_is_deterministic_and_versions(ctx, acceptance_fixture_path):
    client, provider = ctx
    task_id = _prepare_task(client, acceptance_fixture_path)
    provider.register(
        "planning",
        task_id,
        _canned_plan(["invoice.py"], ["invoice.py::calculate_total"]),
    )
    first = client.post(f"/tasks/{task_id}/plan").json()
    second = client.post(f"/tasks/{task_id}/plan").json()
    assert second["version"] == 2
    for key in ("files_to_modify", "steps", "rollback_strategy", "confidence"):
        assert first[key] == second[key]


def test_get_plan_404_before_generate(ctx, acceptance_fixture_path):
    client, _ = ctx
    task_id = _prepare_task(client, acceptance_fixture_path)
    r = client.get(f"/tasks/{task_id}/plan")
    assert r.status_code == 404
    assert r.json()["code"] == "PLAN_NOT_FOUND"
