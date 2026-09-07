"""Verification Agent service (Phase 18,
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 26).

* ``get_or_verify``    -- run the deterministic completion checklist for a
  task's latest patch, persist a ``verification`` row (history chain), write the
  explainability-trace artifact, and move the task to its terminal state
  (``COMPLETED`` / ``AWAITING_APPROVAL`` / ``FAILED``).
* ``resolve_decision`` -- a human APPROVE / REJECT on an ``AWAITING_APPROVAL``
  task: supersede the live ``PARTIAL`` verification with a ``VERIFIED`` /
  ``NOT_VERIFIED`` row and finish the task.

No AI: every criterion is checked against rows Phases 8/10/12/15/16/17 already
persisted. ``Job`` bookkeeping mirrors ``app.services.scoring``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from aegis.schemas.common import Confidence

from app.ai.provider import get_provider
from app.core.config import Settings
from app.core.errors import AppError
from app.core.ids import new_id
from app.implementation.patcher import check_reapplies, touched_paths
from app.implementation.workspace_rw import clone_rw
from app.ingestion.workspace import workspace_dir
from app.models.artifact import ArtifactKind, ArtifactRetention, ArtifactStoreKind
from app.models.job import JobType
from app.models.task import TaskState
from app.repository.artifacts import ArtifactRepository
from app.repository.code_mappings import CodeMappingRepository
from app.repository.engineering_plans import EngineeringPlanRepository
from app.repository.implementations import ImplementationRepository
from app.repository.jobs import JobRepository
from app.repository.regression_plans import RegressionPlanRepository
from app.repository.reviews import ReviewFindingRepository, ReviewRepository
from app.repository.scoring import RiskAssessmentRepository
from app.repository.task_steps import TaskStepRepository
from app.repository.tasks import TaskRepository
from app.repository.test_cases import TestCaseRepository
from app.repository.test_executions import TestExecutionRepository
from app.repository.verifications import VerificationRepository
from app.schemas.implementation import EditOp
from app.schemas.verification import (
    CriterionResult,
    ExplainabilityTrace,
    PlanAlignment,
    VerificationDecision,
    VerificationResult,
)
from app.services import memory as memory_service
from app.services import regression as regression_service
from app.services import review as review_service
from app.services import scoring as scoring_service
from app.services.execution import _reconstruct_implementation
from app.services.repair import _allowed_files
from app.verification import VERIFICATION_MODEL_VERSION
from app.verification.agent import verify
from app.verification.aggregate import failed_criteria_names
from app.verification._criterion import VerificationInputs
from app.verification.errors import (
    VerificationImplementationMissingError,
    VerificationNotAwaitingApprovalError,
    VerificationPlanMissingError,
    VerificationTaskNotFoundError,
)

_RESOLVE_FROM_SETTINGS = object()
_logger = logging.getLogger("app.services.verification")


def _record_memory_safely(
    db: Session, *, settings: Settings, task_id: str, outcome: str
) -> None:
    """Write the Phase 20 engineering-memory record for a task that just
    reached a terminal state. Never fails the caller -- a memory-write problem
    is logged, not propagated."""
    if not settings.memory_enabled:
        return
    try:
        memory_service.record_task(
            db, settings=settings, task_id=task_id, outcome=outcome
        )
    except Exception:  # noqa: BLE001 -- memory is best-effort
        _logger.warning("engineering-memory write failed for task %s", task_id, exc_info=True)


# --------------------------------------------------------------------------- #
# projection
# --------------------------------------------------------------------------- #


def _project_row(row) -> VerificationResult:
    return VerificationResult(
        task_id=row.task_id,
        implementation_version=row.implementation_version,
        verdict=row.verdict,
        criteria=[CriterionResult.model_validate(c) for c in row.criteria],
        plan_alignment=PlanAlignment.model_validate(row.plan_alignment),
        trace=ExplainabilityTrace.model_validate(row.trace),
        trace_artifact_id=row.trace_artifact_id,
        replay_fidelity=row.replay_fidelity,
        confidence=Confidence.model_validate(row.confidence),
        resulting_state=row.resulting_state,
        decision=(
            VerificationDecision.model_validate(row.decision)
            if row.decision
            else None
        ),
        model_version=row.model_version,
        created_at=row.created_at,
    )


# --------------------------------------------------------------------------- #
# input collection
# --------------------------------------------------------------------------- #


def _ensure_upstream(db: Session, *, settings: Settings, task_id: str, provider) -> None:
    """Best-effort: compute the review + score + regression plan so their
    criteria have data. Each is compute-once-cached and idempotent; a missing
    prerequisite (no impact analysis, etc.) just leaves that criterion UNKNOWN.
    """
    for call in (
        lambda: review_service.get_or_review(
            db, settings=settings, task_id=task_id, provider=provider
        ),
        lambda: scoring_service.get_or_score(
            db, settings=settings, task_id=task_id
        ),
        lambda: regression_service.get_or_plan(
            db, settings=settings, task_id=task_id
        ),
    ):
        try:
            call()
        except AppError:
            pass


def _collect_inputs(
    db: Session, *, settings: Settings, task_id: str, impl, plan
) -> VerificationInputs:
    execution = TestExecutionRepository(db).get_latest_by_task(task_id)
    cases = TestCaseRepository(db).list_latest_by_task(task_id)
    regression = RegressionPlanRepository(db).get_by_task(task_id)
    review = ReviewRepository(db).get_by_task(task_id)
    risk = RiskAssessmentRepository(db).get_by_task(task_id)
    mapping = CodeMappingRepository(db).get_by_task(task_id)

    targeted_ids = (
        [
            t["test_id"]
            for t in (regression.tests or [])
            if t.get("classification") == "TARGETED"
        ]
        if regression is not None
        else []
    )

    regression_results: list[dict] = []
    if regression is not None and regression.execution_id:
        reg_exec = TestExecutionRepository(db).get(regression.execution_id)
        if reg_exec is not None:
            regression_results = list(reg_exec.results or [])

    blocking_findings = [
        f"{f.severity} {f.category} {f.file or '-'}"
        for f in ReviewFindingRepository(db).list_for_task(task_id)
        if f.status == "OPEN" and f.severity in ("CRITICAL", "HIGH")
    ]

    # re-derive the workspace to check scope + reproducibility
    source_ws = workspace_dir(impl.snapshot_id, settings)
    ws = clone_rw(impl.snapshot_id, source_ws)
    try:
        _reconstruct_implementation(ws, impl)
        touched = sorted(touched_paths(source_ws, ws))
        edit_ops = [EditOp.model_validate(o) for o in impl.edit_ops]
        reapplies = (
            check_reapplies(source_ws, impl.snapshot_id, edit_ops, ws)
            if edit_ops
            else None
        )
    finally:
        ws.cleanup()

    return VerificationInputs(
        task_id=task_id,
        implementation_version=impl.version,
        snapshot_id=impl.snapshot_id,
        expected_behavior=plan.expected_behavior or "",
        problem_interpretation=plan.problem_interpretation or "",
        rollback_strategy=plan.rollback_strategy or "",
        plan_steps=list(plan.steps or []),
        traceability=dict(impl.traceability or {}),
        scope_violations=list(impl.scope_violations or []),
        touched_files=touched,
        allowed_scope=_allowed_files(db, task_id),
        candidate_paths=[c["path"] for c in (mapping.candidates if mapping else [])],
        has_issue_tests=len(cases) > 0,
        execution_outcome=execution.outcome if execution else None,
        execution_command=execution.command if execution else None,
        execution_id=execution.id if execution else None,
        execution_results=list(execution.results or []) if execution else [],
        targeted_test_ids=targeted_ids,
        regression_present=regression is not None,
        regression_mode=regression.mode if regression else None,
        regression_new_failures=list(regression.new_failures or []) if regression else [],
        regression_subset_justification=(
            regression.subset_justification if regression else None
        ),
        regression_full_suite_count=(
            regression.full_suite_count if regression else 0
        ),
        regression_results=regression_results,
        reapplies=reapplies,
        review_present=review is not None,
        review_blocking=bool(review.blocking) if review else False,
        review_blocking_findings=blocking_findings,
        pcs_value=risk.pcs_value if risk else None,
        crs_value=risk.crs_value if risk else None,
        pcs_min=settings.verification_pcs_min,
        crs_max=settings.verification_crs_max,
    )


# --------------------------------------------------------------------------- #
# get_or_verify
# --------------------------------------------------------------------------- #


def get_or_verify(
    db: Session,
    *,
    settings: Settings,
    task_id: str,
    provider=_RESOLVE_FROM_SETTINGS,
    refresh: bool = False,
) -> VerificationResult:
    if TaskRepository(db).get(task_id) is None:
        raise VerificationTaskNotFoundError(f"task {task_id} not found")

    impl = ImplementationRepository(db).get_latest_by_task(task_id)
    if impl is None:
        raise VerificationImplementationMissingError(
            f"task {task_id} has no implementation to verify "
            f"(POST /tasks/{{id}}/changes)"
        )
    plan = EngineeringPlanRepository(db).get_latest_by_task(task_id)
    if plan is None:
        raise VerificationPlanMissingError(
            f"task {task_id} has no engineering plan (POST /tasks/{{id}}/plan)"
        )

    repo = VerificationRepository(db)
    existing = repo.get_by_task(task_id)
    if existing is not None and not refresh:
        return _project_row(existing)

    if provider is _RESOLVE_FROM_SETTINGS:
        provider = get_provider(settings)

    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.VERIFY.value,
        idempotency_key=f"verify:{task_id}:{new_id()}",
        task_id=task_id,
    )
    jobs.mark_running(job.id)
    try:
        _ensure_upstream(db, settings=settings, task_id=task_id, provider=provider)
        inputs = _collect_inputs(
            db, settings=settings, task_id=task_id, impl=impl, plan=plan
        )
        computation = verify(inputs)

        traces_dir = Path(settings.artifacts_root) / "traces"
        traces_dir.mkdir(parents=True, exist_ok=True)
        trace_path = traces_dir / f"{task_id}.json"
        trace_bytes = json.dumps(
            computation.trace, indent=2, sort_keys=True
        ).encode("utf-8")
        trace_path.write_bytes(trace_bytes)
        artifact = ArtifactRepository(db).create(
            kind=ArtifactKind.TRACE.value,
            store=ArtifactStoreKind.FS.value,
            uri=str(trace_path),
            retention=ArtifactRetention.RETAINED.value,
            snapshot_id=impl.snapshot_id,
            task_id=task_id,
            sha256=hashlib.sha256(trace_bytes).hexdigest(),
            size_bytes=len(trace_bytes),
            content_type="application/json",
        )

        replay_fidelity = (
            None
            if inputs.reapplies is None
            else (1.0 if inputs.reapplies else 0.0)
        )
        row = repo.create_version(
            task_id,
            snapshot_id=impl.snapshot_id,
            implementation_version=impl.version,
            verdict=computation.verdict,
            criteria=[
                {
                    "name": c.name,
                    "verdict": c.verdict,
                    "mandatory": c.mandatory,
                    "detail": c.detail,
                    "evidence": [e.model_dump() for e in c.evidence],
                }
                for c in computation.criteria
            ],
            plan_alignment=computation.alignment,
            trace=computation.trace,
            trace_artifact_id=artifact.id,
            replay_fidelity=replay_fidelity,
            confidence=computation.confidence,
            resulting_state=computation.resulting_state,
            model_version=VERIFICATION_MODEL_VERSION,
        )
    except Exception as exc:  # pragma: no cover - defensive job bookkeeping
        jobs.mark_failed(
            job.id, error={"code": "VERIFICATION_FAILED", "message": str(exc)}
        )
        raise

    steps = TaskStepRepository(db)
    tasks = TaskRepository(db)
    steps.append(
        task_id=task_id, state=TaskState.VERIFYING.value, agent="verification"
    )
    tasks.set_state(task_id, TaskState.VERIFYING.value)

    terminal_reason = None
    if computation.resulting_state == TaskState.FAILED.value:
        terminal_reason = "verification NOT_VERIFIED: " + ", ".join(
            failed_criteria_names(computation.criteria)
        )
    steps.append(
        task_id=task_id,
        state=computation.resulting_state,
        agent="verification",
    )
    tasks.set_state(
        task_id, computation.resulting_state, terminal_reason=terminal_reason
    )
    jobs.mark_succeeded(job.id)

    if computation.resulting_state == TaskState.COMPLETED.value:
        _record_memory_safely(
            db, settings=settings, task_id=task_id, outcome="VERIFIED"
        )

    return _project_row(row)


# --------------------------------------------------------------------------- #
# resolve_decision
# --------------------------------------------------------------------------- #


def resolve_decision(
    db: Session,
    *,
    settings: Settings,
    task_id: str,
    decision: str,
    reason: str,
    actor: str,
) -> VerificationResult:
    task = TaskRepository(db).get(task_id)
    if task is None:
        raise VerificationTaskNotFoundError(f"task {task_id} not found")

    repo = VerificationRepository(db)
    live = repo.get_by_task(task_id)
    if (
        task.state != TaskState.AWAITING_APPROVAL.value
        or live is None
        or live.verdict != "PARTIAL"
    ):
        raise VerificationNotAwaitingApprovalError(
            f"task {task_id} is not awaiting a verification decision "
            f"(state={task.state}, verdict={live.verdict if live else None})"
        )

    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.VERIFY.value,
        idempotency_key=f"verify-decision:{task_id}:{new_id()}",
        task_id=task_id,
    )
    jobs.mark_running(job.id)

    approve = decision == "APPROVE"
    new_verdict = "VERIFIED" if approve else "NOT_VERIFIED"
    new_state = (
        TaskState.COMPLETED.value if approve else TaskState.FAILED.value
    )
    decision_blob = {
        "decision": decision,
        "reason": reason,
        "actor": actor,
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }
    row = repo.create_version(
        task_id,
        snapshot_id=live.snapshot_id,
        implementation_version=live.implementation_version,
        verdict=new_verdict,
        criteria=list(live.criteria),
        plan_alignment=dict(live.plan_alignment),
        trace=dict(live.trace),
        trace_artifact_id=live.trace_artifact_id,
        replay_fidelity=live.replay_fidelity,
        confidence={"value": 1.0, "basis": "FACT"},
        resulting_state=new_state,
        model_version=VERIFICATION_MODEL_VERSION,
        decision=decision_blob,
    )

    steps = TaskStepRepository(db)
    steps.append(
        task_id=task_id, state=new_state, agent="verification:decision"
    )
    terminal_reason = (
        None if approve else f"verification rejected by {actor}: {reason}"
    )
    TaskRepository(db).set_state(
        task_id, new_state, terminal_reason=terminal_reason
    )
    jobs.mark_succeeded(job.id)

    if new_state == TaskState.COMPLETED.value:
        _record_memory_safely(
            db, settings=settings, task_id=task_id, outcome="VERIFIED"
        )

    return _project_row(row)
