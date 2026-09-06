"""Phase 11 integration: GENERATING_TESTS over the acceptance fixture -- full
pipeline through an approved plan + generated implementation, then
POST/GET /tasks/{id}/tests.

See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 19 "Phase-wise testing".
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
    "assumptions": ["the discount argument is a fraction in [0, 1]"],
    "files_to_inspect": ["invoice.py"],
    "files_to_modify": ["invoice.py"],
    "symbols_to_modify": ["invoice.py::calculate_total"],
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


def _canned_test_cases(*, extra=None):
    cases = [
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
    if extra:
        cases.extend(extra)
    return {"test_cases": cases}


@pytest.fixture
def ctx(tmp_path, acceptance_fixture_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'testing_test.db'}")
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


def _prepare_implemented_task(client, provider, acceptance_fixture_path) -> str:
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

    return task_id


def test_generate_tests_produces_valid_cases(ctx, acceptance_fixture_path):
    client, provider = ctx
    task_id = _prepare_implemented_task(client, provider, acceptance_fixture_path)
    provider.register("test_synthesis", task_id, _canned_test_cases())

    gen = client.post(f"/tasks/{task_id}/tests")
    assert gen.status_code == 201, gen.text
    body = gen.json()
    assert body["version"] == 1
    assert len(body["test_cases"]) == 2
    assert {c["status"] for c in body["test_cases"]} == {"GENERATED"}
    assert set(body["targeted_set"]) == {
        "test_discount_at_max",
        "test_discount_above_max",
    }
    assert body["policy_gaps"] == []

    got = client.get(f"/tasks/{task_id}/tests")
    assert got.status_code == 200
    assert got.json()["version"] == 1

    assert client.get(f"/tasks/{task_id}").json()["state"] == "GENERATING_TESTS"


def test_invalid_syntax_case_is_flagged(ctx, acceptance_fixture_path):
    client, provider = ctx
    task_id = _prepare_implemented_task(client, provider, acceptance_fixture_path)
    provider.register(
        "test_synthesis",
        task_id,
        _canned_test_cases(
            extra=[
                {
                    "name": "test_broken",
                    "path": "test_broken.py",
                    "target_symbol": "invoice.py::calculate_total",
                    "kind": "EDGE",
                    "rationale": "deliberately broken",
                    "code": "def test_broken(:\n    pass\n",
                    "evidence": [],
                }
            ]
        ),
    )

    body = client.post(f"/tasks/{task_id}/tests").json()
    broken = next(c for c in body["test_cases"] if c["name"] == "test_broken")
    assert broken["status"] == "INVALID"
    assert broken["invalid_reason"]
    assert "test_broken" not in body["targeted_set"]


def test_tests_before_implementation_is_409(ctx, acceptance_fixture_path):
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

    r = client.post(f"/tasks/{task_id}/tests")
    assert r.status_code == 409
    assert r.json()["code"] == "TEST_GENERATION_IMPLEMENTATION_MISSING"


def test_get_tests_404_before_generate(ctx, acceptance_fixture_path):
    client, provider = ctx
    task_id = _prepare_implemented_task(client, provider, acceptance_fixture_path)
    r = client.get(f"/tasks/{task_id}/tests")
    assert r.status_code == 404
    assert r.json()["code"] == "TEST_GENERATION_NOT_FOUND"


def test_duplicate_name_against_existing_test_is_dropped(ctx, acceptance_fixture_path):
    client, provider = ctx
    task_id = _prepare_implemented_task(client, provider, acceptance_fixture_path)
    # test_invoice.py already defines test_no_discount and
    # test_discount_capped_at_50_percent (test-repositories/aegis-acceptance).
    provider.register(
        "test_synthesis",
        task_id,
        _canned_test_cases(
            extra=[
                {
                    "name": "test_no_discount",
                    "path": "test_no_discount_dup.py",
                    "target_symbol": "invoice.py::calculate_total",
                    "kind": "REGRESSION",
                    "rationale": "duplicate of an existing test name",
                    "code": "def test_no_discount():\n    pass\n",
                    "evidence": [],
                }
            ]
        ),
    )

    body = client.post(f"/tasks/{task_id}/tests").json()
    names = {c["name"] for c in body["test_cases"]}
    assert "test_no_discount" not in names
    assert len(body["test_cases"]) == 2
