"""Autonomous debugging & repair service (docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 22).

``get_or_repair`` runs the bounded repair loop for a task whose latest failing
execution has a Phase 13 ``Investigation``, persists every ``RepairAttempt``,
and returns the derived ``RepairResult`` (REPAIRED or SAFE_STOP). A cached run
is returned unless ``refresh=True``.

The loop's per-iteration test run is an injected ``runner`` callable: the real
one builds a throwaway workspace and runs the Docker sandbox (PARTIALLY_SUPPORTED
without Docker -> the loop SAFE_STOPs cleanly); tests pass a fake.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.provider import get_provider
from app.core.config import Settings
from app.core.ids import new_id
from app.debugging import repair_loop
from app.debugging.errors import (
    RepairInvestigationMissingError,
    RepairTaskNotFoundError,
)
from app.debugging.repair_loop import RunEval
from app.implementation.editor import EditorError, apply_edit_ops
from app.implementation.patcher import unified_diff
from app.implementation.scope_tracker import unplanned_files
from app.implementation.workspace_rw import clone_rw
from app.ingestion.workspace import workspace_dir
from app.models.artifact import ArtifactKind, ArtifactRetention, ArtifactStoreKind
from app.models.job import JobType
from app.models.task import TaskState
from app.repository.artifacts import ArtifactRepository
from app.repository.code_mappings import CodeMappingRepository
from app.repository.engineering_plans import EngineeringPlanRepository
from app.repository.impact_analyses import ImpactAnalysisRepository
from app.repository.implementations import ImplementationRepository
from app.repository.jobs import JobRepository
from app.repository.repair_attempts import RepairAttemptRepository
from app.repository.task_steps import TaskStepRepository
from app.repository.tasks import TaskRepository
from app.repository.test_cases import TestCaseRepository
from app.repository.test_executions import TestExecutionRepository
from app.sandbox.resource_limits import ResourceLimits
from app.sandbox.runner import DockerSandboxRunner
from app.schemas.execution import TestExecutionRun, TestOutcome
from app.schemas.failure import FailureAnalysis
from app.schemas.implementation import EditOp
from app.schemas.repair import RepairAttemptView, RepairResult, SafeStop
from app.services import investigation as investigation_service

_RESOLVE_FROM_SETTINGS = object()
_NON_FAILING = {"PASS", "PARTIALLY_SUPPORTED"}


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #


def _initial_run(execution) -> TestExecutionRun:
    return TestExecutionRun(
        command=execution.command,
        exit_code=execution.exit_code,
        outcome=execution.outcome,
        results=[TestOutcome.model_validate(r) for r in execution.results],
        reason=execution.reason,
        duration_ms=execution.duration_ms,
    )


def _allowed_files(db: Session, task_id: str) -> list[str]:
    scope: set[str] = set()
    plan = EngineeringPlanRepository(db).get_latest_by_task(task_id)
    if plan is not None:
        scope |= set(plan.files_to_modify)
    mapping = CodeMappingRepository(db).get_by_task(task_id)
    if mapping is not None:
        scope |= {c["path"] for c in mapping.candidates}
    impact = ImpactAnalysisRepository(db).get_by_task(task_id)
    if impact is not None:
        scope |= set(impact.changed_set.get("files", []))
    task = TaskRepository(db).get(task_id)
    if task is not None and task.allowed_paths:
        scope |= set(task.allowed_paths)
    return sorted(scope)


# --------------------------------------------------------------------------- #
# Real (Docker-backed) runner
# --------------------------------------------------------------------------- #


def _limits(settings: Settings) -> ResourceLimits:
    return ResourceLimits(
        cpus=settings.sandbox_cpus,
        memory_mb=settings.sandbox_memory_mb,
        pids_limit=settings.sandbox_pids_limit,
        nofile_limit=settings.sandbox_nofile_limit,
        nproc_limit=settings.sandbox_nproc_limit,
        wall_clock_s=settings.sandbox_wall_clock_s,
    )


def _build_docker_runner(db: Session, *, settings: Settings, task_id: str):
    cases = [
        c
        for c in TestCaseRepository(db).list_latest_by_task(task_id)
        if c.status == "GENERATED"
    ]
    impl = ImplementationRepository(db).get_latest_by_task(task_id)
    if impl is None or not cases:
        # nothing runnable -> a runner that reports the sandbox can't help
        def _noop_runner(_ops: list[EditOp]) -> RunEval:
            return RunEval(
                run=TestExecutionRun(
                    command="",
                    exit_code=1,
                    outcome="PARTIALLY_SUPPORTED",
                    reason="no implementation or generated tests to run",
                ),
            )

        return _noop_runner

    snapshot_id = impl.snapshot_id
    source_workspace = workspace_dir(snapshot_id, settings)
    allowed = _allowed_files(db, task_id)

    def _runner(ops: list[EditOp]) -> RunEval:
        ws = clone_rw(snapshot_id, source_workspace)
        try:
            for op_dict in impl.edit_ops:
                try:
                    apply_edit_ops(ws, [EditOp.model_validate(op_dict)])
                except EditorError:
                    pass
            try:
                apply_edit_ops(ws, list(ops))
            except EditorError:
                return RunEval(
                    run=TestExecutionRun(
                        command="",
                        exit_code=1,
                        outcome="ERROR",
                        reason="candidate edit ops could not be applied",
                    ),
                    applied=False,
                )
            violations = sorted(unplanned_files(source_workspace, ws, allowed))
            diff_size = len(unified_diff(source_workspace, ws))
            test_files: list[str] = []
            for case in cases:
                target = ws.path_for(case.path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(case.code, encoding="utf-8")
                test_files.append(case.path)
            run_result = DockerSandboxRunner(
                image=settings.sandbox_image, limits=_limits(settings)
            ).run_tests(ws.root, sorted(set(test_files)))
            return RunEval(
                run=run_result, diff_size=diff_size, scope_violations=violations
            )
        finally:
            ws.cleanup()

    return _runner


# --------------------------------------------------------------------------- #
# Result assembly
# --------------------------------------------------------------------------- #


def _attempt_rows(loop_result) -> list[dict]:
    rows: list[dict] = []
    for a in loop_result.attempts:
        rows.append(
            {
                "iteration": a.iteration,
                "root_cause": a.root_cause,
                "proposal": a.proposal,
                "hypothesis": a.hypothesis,
                "edit_ops": a.edit_ops,
                "outcome": a.outcome,
                "score": {
                    "failing_count": a.score[0],
                    "regression_failures": a.score[1],
                    "diff_size": a.score[2],
                },
            }
        )
    summary = {
        "outcome": loop_result.outcome,
        "best_iteration": loop_result.best_iteration,
        "final_edit_ops": [op.model_dump() for op in loop_result.final_ops],
        "safe_stop": (
            loop_result.safe_stop.model_dump() if loop_result.safe_stop else None
        ),
    }
    if rows:
        rows[-1]["run_summary"] = summary
    else:
        rows.append(
            {
                "iteration": 0,
                "root_cause": loop_result.rca.model_dump(),
                "proposal": {},
                "hypothesis": "(no iteration ran)",
                "edit_ops": [],
                "outcome": "NO_CHANGE",
                "score": {"failing_count": 0, "regression_failures": 0, "diff_size": 0},
                "run_summary": summary,
            }
        )
    return rows


def _view(row) -> RepairAttemptView:
    sc = row.score or {}
    return RepairAttemptView(
        iteration=row.iteration,
        outcome=row.outcome if row.outcome in _ATTEMPT_OUTCOMES else "NO_CHANGE",
        hypothesis=row.hypothesis,
        edit_ops=[EditOp.model_validate(o) for o in row.edit_ops],
        failing_before=0,
        failing_after=sc.get("failing_count", 0),
        regression_failures=sc.get("regression_failures", 0),
        diff_size=sc.get("diff_size", 0),
        score=[
            sc.get("failing_count", 0),
            sc.get("regression_failures", 0),
            sc.get("diff_size", 0),
        ],
        targeted_execution_id=row.targeted_execution_id,
        created_at=row.created_at,
    )


_ATTEMPT_OUTCOMES = {"IMPROVED", "NO_CHANGE", "WORSENED", "GREEN", "REVERTED"}


def _result_from_rows(task_id: str, execution_id: str, rows: list) -> RepairResult:
    summary_row = next((r for r in rows if r.run_summary), rows[-1])
    summary = summary_row.run_summary or {}
    # a synthetic iteration-0 row exists only to carry the summary of a run that
    # produced no real attempts -- don't surface it as an attempt.
    real_rows = [
        r for r in rows if not (r.iteration == 0 and r.run_summary and len(rows) == 1)
    ]
    views = [_view(r) for r in (real_rows or rows)]
    safe_stop = (
        SafeStop.model_validate(summary["safe_stop"])
        if summary.get("safe_stop")
        else None
    )
    return RepairResult(
        task_id=task_id,
        investigation_execution_id=execution_id,
        outcome=summary.get("outcome", "SAFE_STOP"),
        best_iteration=summary.get("best_iteration"),
        attempts=views,
        final_edit_ops=[
            EditOp.model_validate(o) for o in summary.get("final_edit_ops", [])
        ],
        safe_stop=safe_stop,
        created_at=summary_row.created_at,
    )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def get_or_repair(
    db: Session,
    *,
    settings: Settings,
    task_id: str,
    provider=_RESOLVE_FROM_SETTINGS,
    runner=None,
    refresh: bool = False,
) -> RepairResult:
    if TaskRepository(db).get(task_id) is None:
        raise RepairTaskNotFoundError(f"task {task_id} not found")

    execution = TestExecutionRepository(db).get_latest_by_task(task_id)
    if execution is None or execution.outcome in _NON_FAILING:
        raise RepairInvestigationMissingError(
            f"task {task_id} has no failing execution to repair"
        )
    from app.repository.failures import InvestigationRepository

    inv = InvestigationRepository(db).get_by_task_execution(task_id, execution.id)
    if inv is None:
        raise RepairInvestigationMissingError(
            f"task {task_id} needs an investigation first (GET /tasks/{{id}}/failures)"
        )

    repo = RepairAttemptRepository(db)
    existing = repo.list_for_task(task_id)
    if existing and not refresh:
        return _result_from_rows(task_id, execution.id, existing)

    failure_analysis: FailureAnalysis = investigation_service._to_schema(
        inv, execution.id
    )
    if provider is _RESOLVE_FROM_SETTINGS:
        provider = get_provider(settings)
    if runner is None:
        runner = _build_docker_runner(db, settings=settings, task_id=task_id)

    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.REPAIR.value,
        idempotency_key=f"repair:{task_id}:{new_id()}",
        task_id=task_id,
    )
    jobs.mark_running(job.id)

    loop_result = repair_loop.run_repair(
        provider=provider,
        settings=settings,
        failure_analysis=failure_analysis,
        initial_run=_initial_run(execution),
        runner=runner,
        allowed_files=_allowed_files(db, task_id),
        task_key=task_id,
    )

    if loop_result.outcome == "SAFE_STOP" and loop_result.safe_stop is not None:
        _write_safe_stop_artifact(
            db,
            settings=settings,
            task_id=task_id,
            snapshot_id=execution.snapshot_id,
            safe_stop=loop_result.safe_stop,
        )

    rows = repo.replace_for_task(task_id, _attempt_rows(loop_result))
    TaskStepRepository(db).append(
        task_id=task_id, state=TaskState.REPAIRING.value, agent="debugging"
    )
    TaskRepository(db).set_state(task_id, TaskState.REPAIRING.value)
    jobs.mark_succeeded(job.id)
    return _result_from_rows(task_id, execution.id, rows)


def _write_safe_stop_artifact(
    db: Session,
    *,
    settings: Settings,
    task_id: str,
    snapshot_id: str,
    safe_stop: SafeStop,
) -> str:
    out_dir = Path(settings.artifacts_root) / "repairs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{new_id()}-safe_stop.json"
    data = json.dumps(safe_stop.model_dump(), indent=2).encode("utf-8")
    path.write_bytes(data)
    art = ArtifactRepository(db).create(
        kind=ArtifactKind.REPORT.value,
        store=ArtifactStoreKind.FS.value,
        uri=str(path),
        retention=ArtifactRetention.RETAINED.value,
        snapshot_id=snapshot_id,
        task_id=task_id,
        size_bytes=len(data),
        content_type="application/json",
    )
    return art.id
