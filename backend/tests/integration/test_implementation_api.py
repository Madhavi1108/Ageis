"""Phase 10 integration: IMPLEMENTING over the acceptance fixture -- full
pipeline ingest -> analyze -> task -> map -> impact -> plan -> validate
(APPROVED) -> POST/GET /tasks/{id}/changes.

See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 18 "Phase-wise testing".
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


def _canned_plan(files, symbols):
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
        "source": "AI",
        "confidence": {"value": 0.82, "basis": "INFERENCE"},
        "evidence": [
            {"kind": "symbol", "ref": "invoice.py::calculate_total", "detail": "target"}
        ],
    }


def _canned_edit_ops(*, anchor="return price * (1 - discount)"):
    return {
        "edit_ops": [
            {
                "path": "invoice.py",
                "op": "replace",
                "anchor": anchor,
                "new": "discount = min(discount, 0.5)\n    return price * (1 - discount)",
                "plan_step_id": "s1",
                "rationale": "cap discount at 0.5 before applying it",
                "evidence": [
                    {
                        "kind": "symbol",
                        "ref": "invoice.py::calculate_total",
                        "detail": "target",
                    }
                ],
            }
        ]
    }


@pytest.fixture
def ctx(tmp_path, acceptance_fixture_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'implementation_test.db'}")
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


def _prepare_approved_task(client, provider, acceptance_fixture_path) -> str:
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

    provider.register(
        "planning", task_id, _canned_plan(["invoice.py"], ["invoice.py::calculate_total"])
    )
    assert client.post(f"/tasks/{task_id}/plan").status_code == 201
    val = client.post(f"/tasks/{task_id}/plan/validate").json()
    assert val["validation"]["verdict"] == "APPROVED", val

    return task_id


def test_generate_changes_produces_a_real_diff(ctx, acceptance_fixture_path):
    client, provider = ctx
    task_id = _prepare_approved_task(client, provider, acceptance_fixture_path)
    provider.register("implementation", task_id, _canned_edit_ops())

    gen = client.post(f"/tasks/{task_id}/changes")
    assert gen.status_code == 201, gen.text
    body = gen.json()
    assert body["version"] == 1
    assert body["scope_violations"] == []
    assert body["patch"]["touched_paths"] == ["invoice.py"]
    assert "min(discount, 0.5)" in body["patch"]["diff_text"]
    assert body["traceability"] == {"s1": ["invoice.py"]}

    got = client.get(f"/tasks/{task_id}/changes")
    assert got.status_code == 200
    assert got.json()["patch"]["diff_text"] == body["patch"]["diff_text"]

    assert client.get(f"/tasks/{task_id}").json()["state"] == "IMPLEMENTING"


def test_out_of_scope_edit_is_blocked_and_recorded(ctx, acceptance_fixture_path):
    client, provider = ctx
    task_id = _prepare_approved_task(client, provider, acceptance_fixture_path)
    ops = _canned_edit_ops()
    ops["edit_ops"].append(
        {
            "path": "new_unrelated.py",
            "op": "create",
            "new": "# unplanned\n",
            "plan_step_id": "s1",
            "rationale": "sneaky unrelated change",
            "evidence": [],
        }
    )
    provider.register("implementation", task_id, ops)

    gen = client.post(f"/tasks/{task_id}/changes")
    assert gen.status_code == 201, gen.text
    body = gen.json()
    assert body["scope_violations"] == ["new_unrelated.py"]
    # the out-of-scope op is still applied (it's recorded, not silently
    # dropped) -- the plan-scope allowlist check gates *validation*, this is
    # the implementation-time detection layer.
    assert "new_unrelated.py" in body["patch"]["touched_paths"]


def test_changes_before_approved_plan_is_409(ctx, acceptance_fixture_path):
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

    r = client.post(f"/tasks/{task_id}/changes")
    assert r.status_code == 409
    assert r.json()["code"] == "IMPLEMENTATION_PLAN_NOT_APPROVED"


def test_get_changes_404_before_generate(ctx, acceptance_fixture_path):
    client, provider = ctx
    task_id = _prepare_approved_task(client, provider, acceptance_fixture_path)
    r = client.get(f"/tasks/{task_id}/changes")
    assert r.status_code == 404
    assert r.json()["code"] == "IMPLEMENTATION_NOT_FOUND"


def test_regenerate_versions(ctx, acceptance_fixture_path):
    client, provider = ctx
    task_id = _prepare_approved_task(client, provider, acceptance_fixture_path)
    provider.register("implementation", task_id, _canned_edit_ops())
    first = client.post(f"/tasks/{task_id}/changes").json()
    second = client.post(f"/tasks/{task_id}/changes").json()
    assert first["version"] == 1
    assert second["version"] == 2
