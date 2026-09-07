"""Phase 18 integration: the verification verdict + decision flow over HTTP."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.ai.deps import get_ai_provider
from app.ai.provider import MockProvider
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import app
from app.models.base import Base
from app.models.verification import Verification

_PLAN = {
    "problem_interpretation": "cap the discount rate at 0.5",
    "assumptions": [],
    "files_to_inspect": ["invoice.py"],
    "files_to_modify": ["invoice.py"],
    "symbols_to_modify": ["invoice.py::calculate_total"],
    "dependencies": [],
    "steps": [
        {"id": "s1", "description": "clamp", "test_intent": "90% == 50%", "evidence_refs": []}
    ],
    "test_strategy": {"approach": "boundary"},
    "expected_behavior": "the discount never exceeds 0.5",
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
_UNPLANNED_EDIT = {
    "edit_ops": [
        {
            "path": "invoice.py",
            "op": "replace",
            "anchor": "return price * (1 - discount)",
            "new": "discount = min(discount, 0.5)\n    return price * (1 - discount)",
            "plan_step_id": "s1",
            "rationale": "cap",
            "evidence": [],
        },
        {
            "path": "NOTES_out_of_scope.txt",
            "op": "create",
            "new": "scratch\n",
            "plan_step_id": "s1",
            "rationale": "unrelated",
            "evidence": [],
        },
    ]
}


@pytest.fixture
def client(tmp_path, acceptance_fixture_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'verification_test.db'}")
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
            yield c, provider, SessionLocal
    finally:
        app.dependency_overrides.clear()


_VOLATILE = {"created_at", "trace_artifact_id"}


def _strip_ts(obj):
    # created_at moves; trace_artifact_id is a fresh Artifact row per recompute
    if isinstance(obj, dict):
        return {k: _strip_ts(v) for k, v in obj.items() if k not in _VOLATILE}
    if isinstance(obj, list):
        return [_strip_ts(v) for v in obj]
    return obj


def _through_changes(c, provider, fixture, edit_ops) -> str:
    repo_id = c.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(fixture)},
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
    provider.register("implementation", task_id, edit_ops)
    r = c.post(f"/tasks/{task_id}/changes")
    assert r.status_code == 201, r.text
    return task_id


def _count_versions(SessionLocal, task_id: str) -> int:
    with SessionLocal() as s:
        return s.execute(
            select(func.count()).select_from(Verification).where(
                Verification.task_id == task_id
            )
        ).scalar_one()


def test_clean_patch_is_partial_and_awaits_approval(client, acceptance_fixture_path):
    c, provider, _ = client
    task_id = _through_changes(c, provider, acceptance_fixture_path, _CLEAN_EDIT)

    r = c.get(f"/tasks/{task_id}/verification")
    assert r.status_code == 200, r.text
    body = r.json()

    assert {cr["name"] for cr in body["criteria"]} == {
        "acceptance_tests_pass",
        "suite_green",
        "patch_reapplies",
        "scope_clean",
        "review_clean",
        "plan_alignment",
        "score_gate",
    }
    by_name = {cr["name"]: cr for cr in body["criteria"]}
    # deterministic, sandbox-free criteria are decided
    assert by_name["patch_reapplies"]["verdict"] == "PASS"
    assert by_name["scope_clean"]["verdict"] == "PASS"
    assert by_name["review_clean"]["verdict"] == "PASS"
    assert by_name["plan_alignment"]["verdict"] == "PASS"
    # the test suite could not run without Docker -> UNKNOWN, never a false FAIL
    assert by_name["acceptance_tests_pass"]["verdict"] == "UNKNOWN"
    assert by_name["suite_green"]["verdict"] == "UNKNOWN"

    assert body["verdict"] == "PARTIAL"
    assert body["resulting_state"] == "AWAITING_APPROVAL"
    assert body["model_version"] == "verification-model v1.0.0"
    assert body["replay_fidelity"] == 1.0
    assert body["trace_artifact_id"]
    assert set(body["trace"]) == {"why_file", "why_change", "why_test", "why_safe"}
    assert body["trace"]["why_change"] == "cap the discount rate at 0.5"
    assert body["decision"] is None

    assert c.get(f"/tasks/{task_id}").json()["state"] == "AWAITING_APPROVAL"


def test_no_false_complete(client, acceptance_fixture_path):
    """The acceptance rule: nothing is VERIFIED unless every mandatory
    criterion actually passed. Here the suite never ran, so it must not be."""
    c, provider, _ = client
    task_id = _through_changes(c, provider, acceptance_fixture_path, _CLEAN_EDIT)
    assert c.get(f"/tasks/{task_id}/verification").json()["verdict"] != "VERIFIED"


def test_decision_approve_completes_the_task(client, acceptance_fixture_path):
    c, provider, SessionLocal = client
    task_id = _through_changes(c, provider, acceptance_fixture_path, _CLEAN_EDIT)
    c.get(f"/tasks/{task_id}/verification")

    r = c.post(
        f"/tasks/{task_id}/verification/decision",
        json={"decision": "APPROVE", "reason": "sandbox validated manually", "actor": "u@x"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] == "VERIFIED"
    assert body["resulting_state"] == "COMPLETED"
    assert body["decision"]["decision"] == "APPROVE"
    assert body["decision"]["actor"] == "u@x"

    assert c.get(f"/tasks/{task_id}").json()["state"] == "COMPLETED"
    # the live verification is now the VERIFIED one; history kept
    assert c.get(f"/tasks/{task_id}/verification").json()["verdict"] == "VERIFIED"
    assert _count_versions(SessionLocal, task_id) == 2


def test_decision_reject_fails_the_task(client, acceptance_fixture_path):
    c, provider, _ = client
    task_id = _through_changes(c, provider, acceptance_fixture_path, _CLEAN_EDIT)
    c.get(f"/tasks/{task_id}/verification")

    r = c.post(
        f"/tasks/{task_id}/verification/decision",
        json={"decision": "REJECT", "reason": "not confident", "actor": "u@x"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["verdict"] == "NOT_VERIFIED"
    assert r.json()["resulting_state"] == "FAILED"

    t = c.get(f"/tasks/{task_id}").json()
    assert t["state"] == "FAILED"
    assert "rejected by u@x" in t["terminal_reason"]


def test_decision_409_when_not_awaiting_approval(client, acceptance_fixture_path):
    c, provider, _ = client
    task_id = _through_changes(c, provider, acceptance_fixture_path, _CLEAN_EDIT)
    # no verification computed yet -> task is not AWAITING_APPROVAL
    r = c.post(
        f"/tasks/{task_id}/verification/decision",
        json={"decision": "APPROVE", "reason": "x", "actor": "u"},
    )
    assert r.status_code == 409
    assert r.json()["code"] == "VERIFICATION_NOT_AWAITING_APPROVAL"


def test_not_verified_on_unplanned_file(client, acceptance_fixture_path):
    c, provider, _ = client
    task_id = _through_changes(c, provider, acceptance_fixture_path, _UNPLANNED_EDIT)

    body = c.get(f"/tasks/{task_id}/verification").json()
    by_name = {cr["name"]: cr for cr in body["criteria"]}
    assert by_name["scope_clean"]["verdict"] == "FAIL"
    assert by_name["plan_alignment"]["verdict"] == "FAIL"
    assert body["verdict"] == "NOT_VERIFIED"
    assert body["resulting_state"] == "FAILED"
    assert "NOTES_out_of_scope.txt" in body["plan_alignment"]["unplanned_files"]

    t = c.get(f"/tasks/{task_id}").json()
    assert t["state"] == "FAILED"
    assert "NOT_VERIFIED" in t["terminal_reason"]


def test_cache_and_refresh_are_deterministic(client, acceptance_fixture_path):
    c, provider, SessionLocal = client
    task_id = _through_changes(c, provider, acceptance_fixture_path, _CLEAN_EDIT)

    first = c.get(f"/tasks/{task_id}/verification").json()
    cached = c.get(f"/tasks/{task_id}/verification").json()
    assert cached == first
    assert _count_versions(SessionLocal, task_id) == 1

    refreshed = c.get(f"/tasks/{task_id}/verification?refresh=true").json()
    assert _strip_ts(refreshed) == _strip_ts(first)
    # refresh appends a new history row and supersedes the old one
    assert _count_versions(SessionLocal, task_id) == 2


def test_unknown_task_is_404(client):
    c, _, _ = client
    r = c.get("/tasks/nope/verification")
    assert r.status_code == 404
    assert r.json()["code"] == "VERIFICATION_TASK_NOT_FOUND"


def test_without_implementation_is_409(client, acceptance_fixture_path):
    c, _, _ = client
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

    r = c.get(f"/tasks/{task_id}/verification")
    assert r.status_code == 409
    assert r.json()["code"] == "VERIFICATION_IMPLEMENTATION_MISSING"
