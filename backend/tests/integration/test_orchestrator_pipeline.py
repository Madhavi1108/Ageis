"""Phase 21 connectedness anchor (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 29).

With ``sandbox_mode="fake"`` + a MockProvider, the Orchestrator runs the whole
pipeline as one connected workflow: every stage consumes the prior stage's
persisted row, the §4.3 state machine is followed, each ``orchestrator``
TaskStep links to its predecessor's output, and the task reaches a clean
terminal state.
"""

from __future__ import annotations

from app.ai.provider import MockProvider
from app.analysis.analyze import analyze_snapshot
from app.core.config import Settings
from app.ingestion.ingest import ingest_repository
from app.models.task import TaskState
from app.orchestration import orchestrator
from app.repository.engineering_plans import EngineeringPlanRepository
from app.repository.implementations import ImplementationRepository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.repository.task_steps import TaskStepRepository
from app.repository.tasks import TaskRepository
from app.repository.test_cases import TestCaseRepository
from app.repository.test_executions import TestExecutionRepository
from app.repository.verifications import VerificationRepository
from app.schemas.repository import IngestRequest
from app.schemas.task import TaskCreate
from app.services import tasks as tasks_service
from app.services import verification as verification_service

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


def _fake_settings(tmp_path, fixture_parent) -> Settings:
    return Settings(
        ingestion_local_roots=[str(fixture_parent)],
        artifacts_root=str(tmp_path / "artifacts"),
        sandbox_mode="fake",
        _env_file=None,
    )


def _seed(db_session, settings, fixture) -> tuple[str, MockProvider]:
    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL", url_or_path=str(fixture), name="aegis-acceptance"
    )
    res = ingest_repository(
        db_session, repository=repo, request=IngestRequest(), settings=settings
    )
    analyze_snapshot(
        db_session,
        snapshot=SnapshotRepository(db_session).get(res.snapshot_id),
        settings=settings,
    )
    task_md = (fixture / "task.md").read_text(encoding="utf-8")
    task_id = tasks_service.create_task(
        db_session,
        settings=settings,
        payload=TaskCreate(repository_id=repo.id, text=task_md),
    ).task.id

    provider = MockProvider()
    provider.register("planning", task_id, _PLAN)
    provider.register("implementation", task_id, _EDIT_OPS)
    provider.register("test_synthesis", task_id, _TEST_CASES)
    return task_id, provider


def test_orchestrator_runs_the_full_pipeline_connected(
    db_session, tmp_path, acceptance_fixture_path
):
    settings = _fake_settings(tmp_path, acceptance_fixture_path.parent)
    task_id, provider = _seed(db_session, settings, acceptance_fixture_path)

    task = orchestrator.run_task(
        db_session, settings=settings, task_id=task_id, provider=provider
    )

    # the pipeline reached a clean terminal state; approve if it parked
    if task.state == TaskState.AWAITING_APPROVAL.value:
        verification_service.resolve_decision(
            db_session,
            settings=settings,
            task_id=task_id,
            decision="APPROVE",
            reason="fake sandbox validated",
            actor="approver@x",
        )
        task = TaskRepository(db_session).get(task_id)
    assert task.state == TaskState.COMPLETED.value

    # --- FK connectedness: each stage consumed the prior stage's row -------- #
    plan = EngineeringPlanRepository(db_session).get_latest_by_task(task_id)
    impl = ImplementationRepository(db_session).get_latest_by_task(task_id)
    cases = TestCaseRepository(db_session).list_latest_by_task(task_id)
    execution = TestExecutionRepository(db_session).get_latest_by_task(task_id)
    verification = VerificationRepository(db_session).get_by_task(task_id)

    assert impl.plan_id == plan.id
    assert cases and all(c.implementation_id == impl.id for c in cases)
    assert execution.implementation_id == impl.id
    assert execution.outcome == "PASS"  # fake sandbox actually ran the tests
    assert verification.implementation_version == impl.version
    assert verification.verdict in ("VERIFIED",)

    # --- step-ref connectedness: orchestrator steps form an input->output chain ---
    steps = [
        s
        for s in TaskStepRepository(db_session).list_for_task(task_id)
        if s.agent == "orchestrator"
    ]
    states = [s.state for s in steps]
    for expected in ("INGESTING", "ANALYZING", "PLANNING", "IMPLEMENTING",
                     "EXECUTING_TESTS", "REGRESSION_TESTING", "REVIEWING", "VERIFYING"):
        assert expected in states, expected
    refs = [s.input_ref for s in steps if s.state == "IMPLEMENTING"]
    assert plan.id in refs  # the IMPLEMENTING step points back at the plan


def test_orchestrator_is_idempotent_on_a_completed_task(
    db_session, tmp_path, acceptance_fixture_path
):
    settings = _fake_settings(tmp_path, acceptance_fixture_path.parent)
    task_id, provider = _seed(db_session, settings, acceptance_fixture_path)

    orchestrator.run_task(db_session, settings=settings, task_id=task_id, provider=provider)
    t1 = TaskRepository(db_session).get(task_id)
    if t1.state == TaskState.AWAITING_APPROVAL.value:
        verification_service.resolve_decision(
            db_session, settings=settings, task_id=task_id,
            decision="APPROVE", reason="ok", actor="a@x",
        )
    # a second run on a now-terminal task is a no-op
    again = orchestrator.run_task(
        db_session, settings=settings, task_id=task_id, provider=provider
    )
    assert again.state in (TaskState.COMPLETED.value, TaskState.AWAITING_APPROVAL.value)
