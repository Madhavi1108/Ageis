"""The Phase 21 Orchestrator: one connected run of the full pipeline through
the guarded §4.3 state machine (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 29).

``run_task`` sequences every stage service -- each consuming the prior stage's
persisted output -- writing a guarded, ref-linked ``TaskStep`` per transition
and checkpointing the job after each stage (crash-recovery resume). It is a
synchronous function (directly testable, like ``aegis.orchestrator.run_pipeline``);
``worker.py`` is the thin asyncio wrapper.

Docker-less: with ``sandbox_mode="fake"`` the pipeline reaches ``COMPLETED``;
with ``docker`` and no daemon, execution is ``PARTIALLY_SUPPORTED`` and the run
ends at ``AWAITING_APPROVAL`` (verification ``PARTIAL``) -- the honest outcome.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.ai.provider import get_provider
from app.analysis.analyze import analyze_snapshot
from app.core.config import Settings
from app.ingestion.ingest import ingest_repository
from app.models.task import Task, TaskState
from app.orchestration import job_queue, state_machine
from app.repository.analyses import AnalysisRepository
from app.repository.code_mappings import CodeMappingRepository
from app.repository.engineering_plans import EngineeringPlanRepository
from app.repository.implementations import ImplementationRepository
from app.repository.jobs import JobRepository
from app.repository.regression_plans import RegressionPlanRepository
from app.repository.repositories import RepositoryRepository
from app.repository.reviews import ReviewRepository
from app.repository.snapshots import SnapshotRepository

from app.repository.tasks import TaskRepository
from app.repository.test_cases import TestCaseRepository
from app.repository.test_executions import TestExecutionRepository
from app.repository.verifications import VerificationRepository
from app.repository.failures import InvestigationRepository
from app.repository.repair_attempts import RepairAttemptRepository
from app.schemas.repository import IngestRequest
from app.services import impact as impact_service
from app.services import implementation as implementation_service
from app.services import investigation as investigation_service
from app.services import mapping as mapping_service
from app.services import planning as planning_service
from app.services import regression as regression_service
from app.services import repair as repair_service
from app.services import review as review_service
from app.services import scoring as scoring_service
from app.services import testing as testing_service
from app.services import verification as verification_service
from app.services import execution as execution_service

_RESOLVE_FROM_SETTINGS = object()
_logger = logging.getLogger("app.orchestration.orchestrator")

_S = TaskState
_FAILING = {"FAIL", "ERROR", "TIMEOUT", "OOM"}
_ANALYSABLE = ("READY", "PARTIALLY_SUPPORTED")

#: canonical stage order for resume-skipping
STAGE_ORDER = [
    "ingest",
    "analyze",
    "plan",
    "validate",
    "implement",
    "generate_tests",
    "execute",
    "investigate",
    "repair",
    "execute_retry",
    "regression",
    "review",
    "verify",
]

#: linear rank of a workflow state, for resume ("is the task already past this stage?")
_STATE_RANK = {
    _S.PENDING.value: 0,
    _S.QUEUED.value: 1,
    _S.INGESTING.value: 2,
    _S.ANALYZING.value: 3,
    _S.PLANNING.value: 4,
    _S.PLAN_VALIDATION.value: 5,
    _S.IMPLEMENTING.value: 6,
    _S.GENERATING_TESTS.value: 7,
    _S.EXECUTING_TESTS.value: 8,
    _S.INVESTIGATING.value: 8,
    _S.REPAIRING.value: 8,
    _S.REGRESSION_TESTING.value: 9,
    _S.REVIEWING.value: 10,
    _S.VERIFYING.value: 11,
    _S.AWAITING_APPROVAL.value: 12,
}


class _Cancelled(Exception):
    def __init__(self, stage: str) -> None:
        super().__init__(stage)
        self.stage = stage


@dataclass
class _Ctx:
    prev_ref: str | None = None
    done: set[str] = field(default_factory=set)


def run_task(
    db: Session,
    *,
    settings: Settings,
    task_id: str,
    provider=_RESOLVE_FROM_SETTINGS,
    job_id: str | None = None,
    resume_from: str | None = None,
) -> Task:
    if provider is _RESOLVE_FROM_SETTINGS:
        provider = get_provider(settings)

    tasks = TaskRepository(db)
    task = tasks.get(task_id)
    if task is None:
        raise ValueError(f"task {task_id} not found")
    if task.state in state_machine.TERMINAL:
        return task

    ctx = _Ctx()
    if resume_from:
        _logger.info("resuming task %s from checkpoint stage %s", task_id, resume_from)
    # Every stage is idempotent / cache-or-new-version, and _stage() skips any
    # stage the task's *current* state already passed, so a resumed run simply
    # re-enters from the top and fast-forwards to where the crash left it.
    skip_through: set[str] = set()

    def _cancelled() -> bool:
        t = tasks.get(task_id)
        return bool(t and t.cancel_requested) or job_queue.is_job_cancelled(db, job_id)

    def _stage(name: str, to_state: str, run) -> str | None:
        if name in skip_through:
            return None
        if _cancelled():
            raise _Cancelled(name)
        cur = tasks.get(task_id).state
        if cur == to_state:
            pass  # idempotent re-run in place
        elif state_machine.can_transition(cur, to_state):
            state_machine.transition(
                db, task_id, to_state, agent="orchestrator", input_ref=ctx.prev_ref
            )
        elif _STATE_RANK.get(cur, 0) > _STATE_RANK.get(to_state, 0):
            return None  # resume: the task already passed this stage
        else:
            state_machine.assert_transition(cur, to_state)  # -> raises
        ref = run()
        if ref is not None:
            ctx.prev_ref = ref
        job_queue.set_checkpoint(db, job_id, {"stage": name, "state": to_state})
        if job_id is not None:
            JobRepository(db).set_progress(
                job_id, (STAGE_ORDER.index(name) + 1) / len(STAGE_ORDER)
            )
        return ref

    try:
        # PENDING -> QUEUED -> INGESTING (the API run_task already does the first)
        if tasks.get(task_id).state == _S.PENDING.value:
            state_machine.transition(
                db, task_id, _S.QUEUED.value, agent="orchestrator"
            )

        _stage("ingest", _S.INGESTING.value, lambda: _ensure_snapshot(db, settings, task_id))
        _stage("analyze", _S.ANALYZING.value, lambda: _ensure_analysis(db, settings, task_id))

        _run_plan_cycle(db, settings, task_id, provider, job_id, ctx, _stage, skip_through)

        _stage(
            "implement",
            _S.IMPLEMENTING.value,
            lambda: _row_id(
                implementation_service.generate_implementation(
                    db, settings=settings, task_id=task_id, provider=provider
                ),
                lambda: ImplementationRepository(db).get_latest_by_task(task_id),
            ),
        )
        _stage(
            "generate_tests",
            _S.GENERATING_TESTS.value,
            lambda: _first_test_case_id(
                db,
                task_id,
                testing_service.generate_tests(
                    db, settings=settings, task_id=task_id, provider=provider
                ),
            ),
        )

        _stage(
            "execute",
            _S.EXECUTING_TESTS.value,
            lambda: _exec_id(
                db,
                task_id,
                execution_service.execute_tests(db, settings=settings, task_id=task_id),
            ),
        )
        outcome = _latest_exec_outcome(db, task_id)
        if outcome in _FAILING:
            _stage(
                "investigate",
                _S.INVESTIGATING.value,
                lambda: _row_id(
                    investigation_service.get_or_investigate(
                        db, settings=settings, task_id=task_id
                    ),
                    lambda: InvestigationRepository(db).get_latest_by_task(task_id),
                ),
            )
            _stage(
                "repair",
                _S.REPAIRING.value,
                lambda: _last_repair_id(
                    db,
                    task_id,
                    repair_service.get_or_repair(
                        db, settings=settings, task_id=task_id, provider=provider
                    ),
                ),
            )
            _stage(
                "execute_retry",
                _S.EXECUTING_TESTS.value,
                lambda: _exec_id(
                    db,
                    task_id,
                    execution_service.execute_tests(
                        db, settings=settings, task_id=task_id
                    ),
                ),
            )

        _stage(
            "regression",
            _S.REGRESSION_TESTING.value,
            lambda: _row_id(
                regression_service.get_or_plan(
                    db, settings=settings, task_id=task_id, mode="smart"
                ),
                lambda: RegressionPlanRepository(db).get_by_task(task_id),
            ),
        )
        _stage(
            "review",
            _S.REVIEWING.value,
            lambda: _row_id(
                review_service.get_or_review(
                    db, settings=settings, task_id=task_id, provider=provider
                ),
                lambda: ReviewRepository(db).get_by_task(task_id),
            ),
        )

        # score has no workflow state -- run it, no step
        if "verify" not in skip_through:
            try:
                scoring_service.get_or_score(db, settings=settings, task_id=task_id)
            except Exception:  # noqa: BLE001 -- scoring is advisory; verify tolerates it missing
                _logger.warning("scoring failed for task %s", task_id, exc_info=True)

        _stage(
            "verify",
            _S.VERIFYING.value,
            lambda: _row_id(
                verification_service.get_or_verify(
                    db, settings=settings, task_id=task_id, provider=provider
                ),
                lambda: VerificationRepository(db).get_by_task(task_id),
            ),
        )

    except _Cancelled as exc:
        state_machine.transition(
            db,
            task_id,
            _S.CANCELLED.value,
            agent="orchestrator",
            terminal_reason=f"cancelled during {exc.stage}",
        )
        if job_id is not None:
            JobRepository(db).mark_cancelled(job_id)
        return tasks.get(task_id)
    except Exception as exc:  # any stage error -> FAILED (worker decides retry)
        cur = tasks.get(task_id).state
        if cur not in state_machine.TERMINAL:
            state_machine.transition(
                db,
                task_id,
                _S.FAILED.value,
                agent="orchestrator",
                terminal_reason=f"pipeline error: {exc}"[:512],
            )
        raise

    final = tasks.get(task_id)
    if (
        final.state == _S.COMPLETED.value
        and settings.orchestrator_open_pr
        and "verify" not in skip_through
    ):
        _maybe_open_pr(db, settings, task_id)
    return tasks.get(task_id)


# --------------------------------------------------------------------------- #
# stage helpers
# --------------------------------------------------------------------------- #


def _ensure_snapshot(db: Session, settings: Settings, task_id: str) -> str:
    task = TaskRepository(db).get(task_id)
    if task.snapshot_id:
        return task.snapshot_id
    for snap in SnapshotRepository(db).list_for_repository(task.repository_id):
        if snap.status in _ANALYSABLE:
            TaskRepository(db).set_snapshot_id(task_id, snap.id)
            return snap.id
    repo = RepositoryRepository(db).get(task.repository_id)
    assert repo is not None
    res = ingest_repository(
        db, repository=repo, request=IngestRequest(), settings=settings
    )
    TaskRepository(db).set_snapshot_id(task_id, res.snapshot_id)
    return res.snapshot_id


def _ensure_analysis(db: Session, settings: Settings, task_id: str) -> str:
    task = TaskRepository(db).get(task_id)
    snap = SnapshotRepository(db).get(task.snapshot_id)
    assert snap is not None
    if AnalysisRepository(db).get_by_snapshot(snap.id) is None:
        analyze_snapshot(db, snapshot=snap, settings=settings)
    mapping_service.run_mapping(db, settings=settings, task_id=task_id)
    impact_service.get_or_compute_impact(db, settings=settings, task_id=task_id)
    m = CodeMappingRepository(db).get_by_task(task_id)
    return m.id if m is not None else snap.id


def _run_plan_cycle(db, settings, task_id, provider, job_id, ctx, _stage, skip_through):
    revisions = 0
    while True:
        _stage(
            "plan",
            _S.PLANNING.value,
            lambda: _row_id(
                planning_service.generate_plan(
                    db, settings=settings, task_id=task_id, provider=provider
                ),
                lambda: EngineeringPlanRepository(db).get_latest_by_task(task_id),
            ),
        )
        _stage(
            "validate",
            _S.PLAN_VALIDATION.value,
            lambda: _row_id(
                planning_service.validate_plan_for_task(db, task_id),
                lambda: EngineeringPlanRepository(db).get_latest_by_task(task_id),
            ),
        )
        row = EngineeringPlanRepository(db).get_latest_by_task(task_id)
        verdict = row.validation_verdict if row is not None else None
        if verdict == "APPROVED" or "validate" in skip_through:
            return
        if verdict == "REJECTED" or revisions >= settings.orchestrator_max_plan_revisions:
            raise RuntimeError(f"plan not approved (verdict={verdict})")
        revisions += 1
        state_machine.transition(
            db, task_id, _S.PLANNING.value, agent="orchestrator",
            input_ref=ctx.prev_ref,
        )


def _maybe_open_pr(db: Session, settings: Settings, task_id: str) -> None:
    try:
        from app.github.deps import build_github_client
        from app.services import pr as pr_service

        pr_service.create_pr(
            db,
            settings=settings,
            task_id=task_id,
            github_client=build_github_client(settings),
        )
    except Exception:  # noqa: BLE001 -- a PR problem never fails a COMPLETED task
        _logger.warning("orchestrator PR step failed for task %s", task_id, exc_info=True)


# --------------------------------------------------------------------------- #
# tiny row-id extractors
# --------------------------------------------------------------------------- #


def _row_id(_result, fetch_row):
    row = fetch_row()
    return row.id if row is not None else None


def _first_test_case_id(db: Session, task_id: str, _gen) -> str | None:
    cases = TestCaseRepository(db).list_latest_by_task(task_id)
    return cases[0].id if cases else None


def _exec_id(db: Session, task_id: str, _te) -> str | None:
    row = TestExecutionRepository(db).get_latest_by_task(task_id)
    return row.id if row is not None else None


def _latest_exec_outcome(db: Session, task_id: str) -> str | None:
    row = TestExecutionRepository(db).get_latest_by_task(task_id)
    return row.outcome if row is not None else None


def _last_repair_id(db: Session, task_id: str, _rr) -> str | None:
    rows = RepairAttemptRepository(db).list_for_task(task_id)
    return rows[-1].id if rows else None
