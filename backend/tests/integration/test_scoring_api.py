"""Phase 17 integration: PCS / CRS / RHP over the HTTP surface."""

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
        {"id": "s1", "description": "clamp", "test_intent": "90% == 50%", "evidence_refs": []}
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
_SECRET_EDIT = {
    "edit_ops": [
        {
            "path": "invoice.py",
            "op": "replace",
            "anchor": "return price * (1 - discount)",
            "new": 'API_TOKEN = "sk-abcdef0123456789abcdef0123"\n'
            "    return price * (1 - discount)",
            "plan_step_id": "s1",
            "rationale": "oops",
            "evidence": [],
        }
    ]
}


@pytest.fixture
def client(tmp_path, acceptance_fixture_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'scoring_test.db'}")
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


def _strip_ts(obj):
    if isinstance(obj, dict):
        return {k: _strip_ts(v) for k, v in obj.items() if k != "created_at"}
    if isinstance(obj, list):
        return [_strip_ts(v) for v in obj]
    return obj


def _repo_and_snapshot(c, acceptance_fixture_path):
    repo_id = c.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)},
    ).json()["id"]
    sid = c.post(f"/repositories/{repo_id}/snapshots", json={}).json()["snapshot_id"]
    return repo_id, sid


def _through_changes(c, provider, acceptance_fixture_path, edit_ops) -> tuple[str, str]:
    repo_id, sid = _repo_and_snapshot(c, acceptance_fixture_path)
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
    c.get(f"/tasks/{task_id}/review")  # exercise the review-derived signals
    return task_id, repo_id


def test_confidence_and_risk_on_a_clean_patch(client, acceptance_fixture_path):
    c, provider = client
    task_id, _ = _through_changes(c, provider, acceptance_fixture_path, _CLEAN_EDIT)

    conf = c.get(f"/tasks/{task_id}/confidence")
    assert conf.status_code == 200, conf.text
    cbody = conf.json()
    assert 0 <= cbody["value"] <= 100
    assert cbody["classification"] != "BLOCKED"
    assert cbody["hard_gate"] == []
    assert cbody["model_version"] == "scoring-model v1.0.0"
    assert cbody["implementation_version"] == 1
    # the breakdown explains the value
    total = sum(s["contribution"] for s in cbody["per_signal_contributions"])
    assert total * 100 == pytest.approx(cbody["pcs_raw"], abs=0.01)
    assert round(total * 100) == round(cbody["pcs_raw"])
    assert 0.0 <= cbody["overall_confidence"] <= 1.0
    assert cbody["overall_confidence"] < 1.0  # coverage + churn are unavailable here

    risk = c.get(f"/tasks/{task_id}/risk")
    assert risk.status_code == 200, risk.text
    rbody = risk.json()
    assert 0 <= rbody["value"] <= 100
    assert rbody["classification"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    rtotal = sum(s["contribution"] for s in rbody["per_signal_contributions"])
    assert rtotal * 100 == pytest.approx(rbody["crs_raw"], abs=0.01)
    assert round(rtotal * 100) == rbody["value"]
    assert rbody["task_risk_profile"]["scope"] == "task"
    assert 0 <= rbody["task_risk_profile"]["value"] <= 100

    # the score call does not move the task state
    assert c.get(f"/tasks/{task_id}").json()["state"] == "REVIEWING"


def test_scores_are_reproducible(client, acceptance_fixture_path):
    c, provider = client
    task_id, _ = _through_changes(c, provider, acceptance_fixture_path, _CLEAN_EDIT)

    first = c.get(f"/tasks/{task_id}/confidence").json()
    cached = c.get(f"/tasks/{task_id}/confidence").json()
    refreshed = c.get(f"/tasks/{task_id}/confidence?refresh=true").json()
    assert cached == first
    assert _strip_ts(refreshed) == _strip_ts(first)


def test_secret_literal_blocks_the_patch(client, acceptance_fixture_path):
    c, provider = client
    task_id, _ = _through_changes(c, provider, acceptance_fixture_path, _SECRET_EDIT)

    cbody = c.get(f"/tasks/{task_id}/confidence").json()
    assert cbody["classification"] == "BLOCKED"
    assert cbody["value"] <= 40
    assert "unresolved_critical_review_finding" in cbody["hard_gate"]
    assert cbody["security_gate"] == 0.0


def test_repository_health(client, acceptance_fixture_path):
    c, provider = client
    _, repo_id = _through_changes(c, provider, acceptance_fixture_path, _CLEAN_EDIT)

    h = c.get(f"/repositories/{repo_id}/health")
    assert h.status_code == 200, h.text
    body = h.json()
    assert 0 <= body["value"] <= 100
    assert body["scope"] == "repository"
    names = {s["name"] for s in body["subscores"]}
    assert names == {
        "maintainability",
        "test_coverage",
        "inverse_dependency_coupling",
        "churn_stability",
        "documentation_ratio",
        "ci_presence",
    }
    assert _strip_ts(c.get(f"/repositories/{repo_id}/health").json()) == _strip_ts(body)
    assert _strip_ts(
        c.get(f"/repositories/{repo_id}/health?refresh=true").json()
    ) == _strip_ts(body)


def test_confidence_without_implementation_is_409(client, acceptance_fixture_path):
    c, _ = client
    repo_id, sid = _repo_and_snapshot(c, acceptance_fixture_path)
    c.post(f"/repositories/{repo_id}/snapshots/{sid}/analysis", json={})
    task_md = (acceptance_fixture_path / "task.md").read_text(encoding="utf-8")
    task_id = c.post("/tasks", json={"repository_id": repo_id, "text": task_md}).json()[
        "task"
    ]["id"]

    r = c.get(f"/tasks/{task_id}/confidence")
    assert r.status_code == 409
    assert r.json()["code"] == "SCORING_IMPLEMENTATION_MISSING"


def test_health_without_analysis_is_409(client, acceptance_fixture_path):
    c, _ = client
    repo_id, _sid = _repo_and_snapshot(c, acceptance_fixture_path)  # no /analysis call
    r = c.get(f"/repositories/{repo_id}/health")
    assert r.status_code == 409
    assert r.json()["code"] == "SCORING_ANALYSIS_MISSING"


def test_unknown_task_and_repo_are_404(client):
    c, _ = client
    r1 = c.get("/tasks/nope/risk")
    assert r1.status_code == 404 and r1.json()["code"] == "SCORING_TASK_NOT_FOUND"
    r2 = c.get("/repositories/nope/health")
    assert r2.status_code == 404 and r2.json()["code"] == "SCORING_REPOSITORY_NOT_FOUND"
