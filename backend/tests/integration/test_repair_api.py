"""Phase 14 integration: the bounded repair loop over a seeded failing task.

Docker is unavailable here: the API path (real runner) SAFE_STOPs with
"sandbox unavailable"; the REPAIRED / persisted-ledger paths are exercised at
the service level with a fake runner.
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
from app.debugging.repair_loop import RunEval
from app.main import app
from app.models.artifact import ArtifactKind, ArtifactRetention, ArtifactStoreKind
from app.models.base import Base
from app.repository.artifacts import ArtifactRepository
from app.repository.implementations import ImplementationRepository
from app.repository.test_executions import TestExecutionRepository
from app.schemas.execution import TestExecutionRun, TestOutcome
from app.services import repair as repair_service

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
            "test_intent": "90% behaves like 50%",
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
            "path": "test_invoice_negative.py",
            "target_symbol": "invoice.py::calculate_total",
            "kind": "NEGATIVE",
            "rationale": "cap",
            "code": "from invoice import calculate_total\n\n\ndef test_above_max():\n"
            "    assert calculate_total(100.0, 0.9) == 50.0\n",
            "evidence": [],
        }
    ]
}
_RCA = {
    "hypotheses": [
        {
            "statement": "calculate_total does not cap the discount",
            "label": "INFERENCE",
            "evidence": [
                {
                    "kind": "symbol",
                    "ref": "invoice.py::calculate_total",
                    "detail": "assertion detail",
                }
            ],
            "rank": 0,
        }
    ],
    "most_likely_index": 0,
    "open_questions": [],
    "confidence": {"value": 0.6, "basis": "INFERENCE"},
    "evidence": [],
}
_PROPOSAL = {
    "target_hypothesis": "calculate_total does not cap the discount",
    "edit_ops": [
        {
            "path": "invoice.py",
            "op": "replace",
            "anchor": "return price * (1 - discount)",
            "new": "discount = min(discount, 0.5)\n    return price * (1 - discount)",
            "plan_step_id": "repair",
            "rationale": "cap the discount",
            "evidence": [],
        }
    ],
    "expected_effect": "the boundary test passes",
    "risk_notes": [],
    "confidence": {"value": 0.7, "basis": "INFERENCE"},
}

_FAIL_STDOUT = """\
=================================== FAILURES ===================================
____________________________ test_above_max ____________________________

>       assert calculate_total(100.0, 0.9) == 50.0
E       assert 10.0 == 50.0
E        +  where 10.0 = calculate_total(100.0, 0.9)

test_invoice_negative.py:5: AssertionError
=========================== short test summary info ============================
FAILED test_invoice_negative.py::test_above_max - assert 10.0 == 50.0
"""


@pytest.fixture
def ctx(tmp_path, acceptance_fixture_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'repair_test.db'}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    provider = MockProvider()
    artifacts_root = tmp_path / "artifacts"

    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def _get_settings():
        return Settings(
            ingestion_local_roots=[str(acceptance_fixture_path.parent)],
            artifacts_root=str(artifacts_root),
            _env_file=None,
        )

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_settings] = _get_settings
    app.dependency_overrides[get_ai_provider] = lambda: provider
    try:
        with TestClient(app) as client:
            yield client, provider, SessionLocal, artifacts_root, _get_settings()
    finally:
        app.dependency_overrides.clear()


def _prepare_investigated_task(
    client, provider, SessionLocal, artifacts_root, acceptance_fixture_path
) -> str:
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
    client.post("/analysis/map", json={"task_id": task_id})
    client.get(f"/tasks/{task_id}/impact")
    provider.register("planning", task_id, _PLAN)
    client.post(f"/tasks/{task_id}/plan")
    client.post(f"/tasks/{task_id}/plan/validate")
    provider.register("implementation", task_id, _EDIT_OPS)
    client.post(f"/tasks/{task_id}/changes")
    provider.register("test_synthesis", task_id, _TESTS)
    client.post(f"/tasks/{task_id}/tests")

    # seed a FAIL execution + stdout artifact, then run the Phase 13 investigation
    db = SessionLocal()
    try:
        impl = ImplementationRepository(db).get_latest_by_task(task_id)
        artifacts_root.mkdir(parents=True, exist_ok=True)
        p = artifacts_root / "fail-stdout.txt"
        p.write_text(_FAIL_STDOUT, encoding="utf-8")
        art = ArtifactRepository(db).create(
            kind=ArtifactKind.STDIO.value,
            store=ArtifactStoreKind.FS.value,
            uri=str(p),
            retention=ArtifactRetention.RETAINED.value,
            snapshot_id=impl.snapshot_id,
            task_id=task_id,
            size_bytes=len(_FAIL_STDOUT),
            content_type="text/plain",
        )
        TestExecutionRepository(db).create_version(
            task_id,
            snapshot_id=impl.snapshot_id,
            implementation_id=impl.id,
            command="pytest",
            exit_code=1,
            outcome="FAIL",
            results=[
                {
                    "test_id": "test_invoice_negative.py::test_above_max",
                    "outcome": "FAIL",
                }
            ],
            reason=None,
            duration_ms=20,
            stdout_artifact_id=art.id,
            stderr_artifact_id=None,
        )
    finally:
        db.close()
    assert client.get(f"/tasks/{task_id}/failures").status_code == 200
    return task_id


def _run(ids, outcome="FAIL"):
    return TestExecutionRun(
        command="pytest",
        exit_code=0 if outcome == "PASS" else 1,
        outcome=outcome,
        results=[TestOutcome(test_id=i, outcome="FAIL") for i in ids],
    )


def test_repaired_path_persists_ledger(ctx, acceptance_fixture_path):
    client, provider, SessionLocal, artifacts_root, settings = ctx
    task_id = _prepare_investigated_task(
        client, provider, SessionLocal, artifacts_root, acceptance_fixture_path
    )
    provider.register("rca", task_id, _RCA)
    provider.register("repair", task_id, _PROPOSAL)

    script = [RunEval(run=_run(["t0"])), RunEval(run=_run([], "PASS"))]
    box = {"i": 0}

    def fake_runner(_ops):
        r = script[min(box["i"], len(script) - 1)]
        box["i"] += 1
        return r

    db = SessionLocal()
    try:
        result = repair_service.get_or_repair(
            db,
            settings=settings,
            task_id=task_id,
            provider=provider,
            runner=fake_runner,
        )
    finally:
        db.close()

    assert result.outcome == "REPAIRED"
    assert result.best_iteration is not None
    assert result.final_edit_ops

    got = client.get(f"/tasks/{task_id}/repairs")
    assert got.status_code == 200
    body = got.json()
    assert body["outcome"] == "REPAIRED"
    assert [a["outcome"] for a in body["attempts"]][-1] == "GREEN"
    assert client.get(f"/tasks/{task_id}").json()["state"] == "REPAIRING"


def test_safe_stop_path_writes_artifact(ctx, acceptance_fixture_path):
    client, provider, SessionLocal, artifacts_root, settings = ctx
    task_id = _prepare_investigated_task(
        client, provider, SessionLocal, artifacts_root, acceptance_fixture_path
    )
    provider.register("rca", task_id, _RCA)
    provider.register("repair", task_id, _PROPOSAL)

    db = SessionLocal()
    try:
        result = repair_service.get_or_repair(
            db,
            settings=settings,
            task_id=task_id,
            provider=provider,
            runner=lambda _ops: RunEval(run=_run(["t0", "t1"])),  # never improves
        )
    finally:
        db.close()

    assert result.outcome == "SAFE_STOP"
    assert result.safe_stop is not None
    assert len(result.attempts) <= settings.repair_max_iterations
    arts = list((artifacts_root / "repairs").glob("*-safe_stop.json"))
    assert arts, "a SAFE_STOP artifact should have been written"


def test_api_without_docker_safe_stops(ctx, acceptance_fixture_path):
    client, provider, SessionLocal, artifacts_root, _settings = ctx
    task_id = _prepare_investigated_task(
        client, provider, SessionLocal, artifacts_root, acceptance_fixture_path
    )
    provider.register("rca", task_id, _RCA)
    provider.register("repair", task_id, _PROPOSAL)

    r = client.get(f"/tasks/{task_id}/repairs")
    assert r.status_code == 200
    assert r.json()["outcome"] == "SAFE_STOP"
    assert "sandbox" in r.json()["safe_stop"]["reason"].lower()


def test_repairs_before_investigation_is_409(ctx, acceptance_fixture_path):
    client, provider, *_ = ctx
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

    r = client.get(f"/tasks/{task_id}/repairs")
    assert r.status_code == 409
    assert r.json()["code"] == "REPAIR_INVESTIGATION_MISSING"
