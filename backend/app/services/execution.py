"""Secure execution service (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 20).

* ``execute_tests`` -- reconstruct the implemented workspace, write the
  latest GENERATED test cases into it, run them in the Docker sandbox (or
  PARTIALLY_SUPPORTED if Docker is unavailable), persist a new TestExecution
  version.
* ``get_execution``      -- read one persisted execution by its own id.
* ``list_executions``    -- every persisted execution for a task, newest first.

Job bookkeeping mirrors app.services.testing.generate_tests. A
PARTIALLY_SUPPORTED/TIMEOUT/INFRA_ERROR outcome is not an AppError -- it is a
valid, persisted terminal-ish result (docs/EXECUTION_MODEL.md Section 8), so
the job is marked SUCCEEDED either way; only a genuine precondition failure
(no tests to run) raises.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.ids import new_id
from app.implementation.editor import EditorError, apply_edit_op
from app.implementation.workspace_rw import clone_rw
from app.ingestion.workspace import workspace_dir
from app.models.artifact import ArtifactKind, ArtifactRetention, ArtifactStoreKind
from app.models.implementation import Implementation as ImplementationRow
from app.models.job import JobType
from app.models.task import TaskState
from app.repository.artifacts import ArtifactRepository
from app.repository.implementations import ImplementationRepository
from app.repository.jobs import JobRepository
from app.repository.task_steps import TaskStepRepository
from app.repository.tasks import TaskRepository
from app.repository.test_cases import TestCaseRepository
from app.repository.test_executions import TestExecutionRepository
from app.schemas.implementation import EditOp
from app.sandbox.errors import (
    TestExecutionNotFoundError,
    TestExecutionTaskNotFoundError,
    TestExecutionTestsMissingError,
)
from app.sandbox.resource_limits import ResourceLimits
from app.sandbox.runner import DockerSandboxRunner
from app.schemas.execution import TestExecution


def _row_to_schema(row) -> TestExecution:
    return TestExecution(
        id=row.id,
        task_id=row.task_id,
        snapshot_id=row.snapshot_id,
        implementation_id=row.implementation_id,
        version=row.version,
        command=row.command,
        exit_code=row.exit_code,
        outcome=row.outcome,
        results=row.results,
        reason=row.reason,
        duration_ms=row.duration_ms,
        stdout_artifact_id=row.stdout_artifact_id,
        stderr_artifact_id=row.stderr_artifact_id,
        created_at=row.created_at,
    )


def _limits_from_settings(settings: Settings) -> ResourceLimits:
    return ResourceLimits(
        cpus=settings.sandbox_cpus,
        memory_mb=settings.sandbox_memory_mb,
        pids_limit=settings.sandbox_pids_limit,
        nofile_limit=settings.sandbox_nofile_limit,
        nproc_limit=settings.sandbox_nproc_limit,
        wall_clock_s=settings.sandbox_wall_clock_s,
    )


def _store_stdio_artifact(
    db: Session,
    *,
    settings: Settings,
    task_id: str,
    snapshot_id: str,
    text: str,
    label: str,
) -> str | None:
    if not text:
        return None
    executions_dir = Path(settings.artifacts_root) / "executions"
    executions_dir.mkdir(parents=True, exist_ok=True)
    path = executions_dir / f"{new_id()}-{label}.txt"
    data = text.encode("utf-8")
    path.write_bytes(data)
    artifact = ArtifactRepository(db).create(
        kind=ArtifactKind.STDIO.value,
        store=ArtifactStoreKind.FS.value,
        uri=str(path),
        retention=ArtifactRetention.RETAINED.value,
        snapshot_id=snapshot_id,
        task_id=task_id,
        size_bytes=len(data),
        content_type="text/plain",
    )
    return artifact.id


def _reconstruct_implementation(ws, impl_row: ImplementationRow) -> None:
    for op_dict in impl_row.edit_ops:
        try:
            apply_edit_op(ws, EditOp.model_validate(op_dict))
        except EditorError:
            pass  # best-effort reconstruction; a failed op here was never applied originally


def execute_tests(
    db: Session,
    *,
    settings: Settings,
    task_id: str,
) -> TestExecution:
    task = TaskRepository(db).get(task_id)
    if task is None:
        raise TestExecutionTaskNotFoundError(f"task {task_id} not found")

    cases = TestCaseRepository(db).list_latest_by_task(task_id)
    runnable = [c for c in cases if c.status == "GENERATED"]
    if not runnable:
        raise TestExecutionTestsMissingError(
            f"task {task_id} needs generated tests (POST /tasks/{{id}}/tests) "
            "before execution -- none are GENERATED"
        )

    implementation_id = runnable[0].implementation_id
    snapshot_id = runnable[0].snapshot_id
    impl_row = ImplementationRepository(db).get(implementation_id)
    assert impl_row is not None

    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.EXECUTE_TESTS.value,
        idempotency_key=f"exectests:{task_id}:{new_id()}",
        task_id=task_id,
    )
    jobs.mark_running(job.id)

    source_workspace = workspace_dir(snapshot_id, settings)
    ws = clone_rw(snapshot_id, source_workspace)
    try:
        _reconstruct_implementation(ws, impl_row)

        touched_paths: list[str] = []
        for case in runnable:
            target = ws.path_for(case.path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(case.code, encoding="utf-8")
            touched_paths.append(case.path)
        test_command = sorted(set(touched_paths))

        runner = DockerSandboxRunner(
            image=settings.sandbox_image, limits=_limits_from_settings(settings)
        )
        run_result = runner.run_tests(ws.root, test_command)

        stdout_artifact_id = _store_stdio_artifact(
            db,
            settings=settings,
            task_id=task_id,
            snapshot_id=snapshot_id,
            text=run_result.stdout,
            label="stdout",
        )
        stderr_artifact_id = _store_stdio_artifact(
            db,
            settings=settings,
            task_id=task_id,
            snapshot_id=snapshot_id,
            text=run_result.stderr,
            label="stderr",
        )

        row = TestExecutionRepository(db).create_version(
            task_id,
            snapshot_id=snapshot_id,
            implementation_id=implementation_id,
            command=run_result.command,
            exit_code=run_result.exit_code,
            outcome=run_result.outcome,
            results=[r.model_dump() for r in run_result.results],
            reason=run_result.reason,
            duration_ms=run_result.duration_ms,
            stdout_artifact_id=stdout_artifact_id,
            stderr_artifact_id=stderr_artifact_id,
        )

        TaskStepRepository(db).append(
            task_id=task_id, state=TaskState.EXECUTING_TESTS.value, agent="sandbox"
        )
        TaskRepository(db).set_state(task_id, TaskState.EXECUTING_TESTS.value)
        jobs.mark_succeeded(job.id)

        return _row_to_schema(row)
    finally:
        ws.cleanup()


def get_execution(db: Session, execution_id: str) -> TestExecution:
    row = TestExecutionRepository(db).get(execution_id)
    if row is None:
        raise TestExecutionNotFoundError(f"no execution {execution_id}")
    return _row_to_schema(row)


def list_executions(db: Session, task_id: str) -> list[TestExecution]:
    if TaskRepository(db).get(task_id) is None:
        raise TestExecutionTaskNotFoundError(f"task {task_id} not found")
    rows = TestExecutionRepository(db).list_for_task(task_id)
    return [_row_to_schema(r) for r in rows]
