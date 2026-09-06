"""Phase 13 integration: INVESTIGATING over a seeded failing TestExecution.

Docker is unavailable here, so a real failing run cannot be produced; the test
seeds a FAIL TestExecution row + a canned pytest-output artifact (the
acceptance repo's boundary failure) and drives GET /tasks/{id}/failures.
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
from app.models.artifact import ArtifactKind, ArtifactRetention, ArtifactStoreKind
from app.models.base import Base
from app.repository.artifacts import ArtifactRepository
from app.repository.implementations import ImplementationRepository
from app.repository.test_executions import TestExecutionRepository

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
    "test_strategy": {"approach": "boundary test at discount=0.9"},
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
            "rationale": "cap discount at 0.5",
            "evidence": [],
        }
    ]
}
_TEST_CASES = {
    "test_cases": [
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
        }
    ]
}

_FAIL_STDOUT = """\
=================================== FAILURES ===================================
___________________________ test_discount_above_max ___________________________

    def test_discount_above_max():
>       assert calculate_total(100.0, 0.9) == 50.0
E       assert 10.000000000000009 == 50.0
E        +  where 10.000000000000009 = calculate_total(100.0, 0.9)

test_invoice_negative.py:5: AssertionError
=========================== short test summary info ============================
FAILED test_invoice_negative.py::test_discount_above_max - assert 10.0 == 50.0
========================= 1 failed in 0.03s =========================
"""

_CAUSAL_WORDS = ("because", "caused by", "root cause", "the bug is", "due to a bug")


@pytest.fixture
def ctx(tmp_path, acceptance_fixture_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'investigation_test.db'}")
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
            yield client, provider, SessionLocal, artifacts_root
    finally:
        app.dependency_overrides.clear()


def _prepare(client, provider, acceptance_fixture_path) -> str:
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
    provider.register("test_synthesis", task_id, _TEST_CASES)
    client.post(f"/tasks/{task_id}/tests")
    return task_id


def _seed_failing_execution(SessionLocal, artifacts_root, task_id: str) -> str:
    db = SessionLocal()
    try:
        impl = ImplementationRepository(db).get_latest_by_task(task_id)
        assert impl is not None
        artifacts_root.mkdir(parents=True, exist_ok=True)
        stdout_path = artifacts_root / "seeded-stdout.txt"
        stdout_path.write_text(_FAIL_STDOUT, encoding="utf-8")
        art = ArtifactRepository(db).create(
            kind=ArtifactKind.STDIO.value,
            store=ArtifactStoreKind.FS.value,
            uri=str(stdout_path),
            retention=ArtifactRetention.RETAINED.value,
            snapshot_id=impl.snapshot_id,
            task_id=task_id,
            size_bytes=len(_FAIL_STDOUT),
            content_type="text/plain",
        )
        row = TestExecutionRepository(db).create_version(
            task_id,
            snapshot_id=impl.snapshot_id,
            implementation_id=impl.id,
            command="pytest test_invoice_negative.py",
            exit_code=1,
            outcome="FAIL",
            results=[
                {
                    "test_id": "test_invoice_negative.py::test_discount_above_max",
                    "outcome": "FAIL",
                }
            ],
            reason=None,
            duration_ms=30,
            stdout_artifact_id=art.id,
            stderr_artifact_id=None,
        )
        return row.id
    finally:
        db.close()


def test_investigation_identifies_failure_without_inventing_cause(
    ctx, acceptance_fixture_path
):
    client, provider, SessionLocal, artifacts_root = ctx
    task_id = _prepare(client, provider, acceptance_fixture_path)
    _seed_failing_execution(SessionLocal, artifacts_root, task_id)

    r = client.get(f"/tasks/{task_id}/failures")
    assert r.status_code == 200, r.text
    fa = r.json()

    assert len(fa["failures"]) == 1
    f0 = fa["failures"][0]
    assert "test_discount_above_max" in f0["test_name"]
    assert f0["failure_type"] == "ASSERTION"
    assert f0["exception_type"] == "AssertionError"

    assert fa["classification"]["primary_symbol_id"] == "invoice.py::calculate_total"
    assert fa["facts"]
    assert all(isinstance(x, str) and x for x in fa["facts"])
    assert fa["inferences"]
    for inf in fa["inferences"]:
        assert not any(w in inf.lower() for w in _CAUSAL_WORDS), inf

    assert client.get(f"/tasks/{task_id}").json()["state"] == "INVESTIGATING"


def test_investigation_is_cached_and_refreshable(ctx, acceptance_fixture_path):
    client, provider, SessionLocal, artifacts_root = ctx
    task_id = _prepare(client, provider, acceptance_fixture_path)
    _seed_failing_execution(SessionLocal, artifacts_root, task_id)

    first = client.get(f"/tasks/{task_id}/failures").json()
    second = client.get(f"/tasks/{task_id}/failures").json()
    refreshed = client.get(f"/tasks/{task_id}/failures?refresh=true").json()
    for key in ("failures", "facts", "inferences", "classification", "evidence"):
        assert first[key] == second[key] == refreshed[key]


def test_no_failing_execution_is_409(ctx, acceptance_fixture_path):
    client, provider, SessionLocal, artifacts_root = ctx
    task_id = _prepare(client, provider, acceptance_fixture_path)
    # the only execution is the real one -> PARTIALLY_SUPPORTED (no Docker)
    client.post(f"/tasks/{task_id}/executions")

    r = client.get(f"/tasks/{task_id}/failures")
    assert r.status_code == 409
    assert r.json()["code"] == "NO_FAILING_EXECUTION"


def test_unknown_task_is_404(ctx):
    client, *_ = ctx
    r = client.get("/tasks/nope/failures")
    assert r.status_code == 404
    assert r.json()["code"] == "FAILURE_TASK_NOT_FOUND"
