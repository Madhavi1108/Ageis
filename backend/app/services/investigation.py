"""Failure-investigation service (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 21).

``get_or_investigate`` is the single entry point behind
``GET /tasks/{id}/failures``: it finds the latest *failing* TestExecution,
parses + bundles it into an Investigation (computing + persisting on first
access, or with ``?refresh=1``), and returns the FailureAnalysis. No AI.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.ids import new_id
from app.debugging import investigate as investigate_engine
from app.debugging.errors import FailureTaskNotFoundError, NoFailingExecutionError
from app.models.artifact import ArtifactKind, ArtifactRetention, ArtifactStoreKind
from app.models.job import JobType
from app.models.task import TaskState
from app.repository.artifacts import ArtifactRepository
from app.repository.failures import FailureRepository, InvestigationRepository
from app.repository.implementations import ImplementationRepository
from app.repository.jobs import JobRepository
from app.repository.patches import PatchRepository
from app.repository.task_steps import TaskStepRepository
from app.repository.tasks import TaskRepository
from app.repository.test_executions import TestExecutionRepository
from app.schemas.failure import FailureAnalysis, FailureRecord

_NON_FAILING = {"PASS", "PARTIALLY_SUPPORTED"}


def _read_artifact_text(db: Session, artifact_id: str | None) -> str:
    if not artifact_id:
        return ""
    art = ArtifactRepository(db).get(artifact_id)
    if art is None:
        return ""
    try:
        return Path(art.uri).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _store_traceback(
    db: Session, *, settings: Settings, task_id: str, snapshot_id: str, text: str
) -> str | None:
    if not text:
        return None
    out_dir = Path(settings.artifacts_root) / "investigations"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{new_id()}-traceback.txt"
    data = text.encode("utf-8")
    path.write_bytes(data)
    art = ArtifactRepository(db).create(
        kind=ArtifactKind.TRACE.value,
        store=ArtifactStoreKind.FS.value,
        uri=str(path),
        retention=ArtifactRetention.RETAINED.value,
        snapshot_id=snapshot_id,
        task_id=task_id,
        size_bytes=len(data),
        content_type="text/plain",
    )
    return art.id


def _diff_text_for(db: Session, implementation_id: str) -> str:
    patch = PatchRepository(db).get_by_implementation(implementation_id)
    if patch is None or not patch.artifact_id:
        return ""
    return _read_artifact_text(db, patch.artifact_id)


def _to_schema(inv_row, execution_id: str) -> FailureAnalysis:
    return FailureAnalysis(
        task_id=inv_row.task_id,
        execution_id=execution_id,
        failures=[FailureRecord.model_validate(r) for r in inv_row.failures],
        facts=inv_row.facts,
        inferences=inv_row.inferences,
        classification=inv_row.classification,
        evidence=inv_row.evidence,
        created_at=inv_row.created_at,
    )


def get_or_investigate(
    db: Session, *, settings: Settings, task_id: str, refresh: bool = False
) -> FailureAnalysis:
    if TaskRepository(db).get(task_id) is None:
        raise FailureTaskNotFoundError(f"task {task_id} not found")

    execution = TestExecutionRepository(db).get_latest_by_task(task_id)
    if execution is None:
        raise NoFailingExecutionError(
            f"task {task_id} has no test execution yet (POST /tasks/{{id}}/executions)"
        )
    if execution.outcome in _NON_FAILING:
        raise NoFailingExecutionError(
            f"task {task_id}'s latest execution outcome is {execution.outcome} -- "
            "nothing to investigate"
        )

    inv_repo = InvestigationRepository(db)
    existing = inv_repo.get_by_task_execution(task_id, execution.id)
    if existing is not None and not refresh:
        return _to_schema(existing, execution.id)

    impl = ImplementationRepository(db).get(execution.implementation_id)
    touched_paths = (
        {op.get("path") for op in impl.edit_ops if op.get("path")} if impl else set()
    )
    diff_text = _diff_text_for(db, execution.implementation_id) if impl else ""

    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.INVESTIGATE.value,
        idempotency_key=f"investigate:{task_id}:{new_id()}",
        task_id=task_id,
    )
    jobs.mark_running(job.id)

    result = investigate_engine.run(
        db,
        execution_row=execution,
        implementation_version=impl.version if impl else 0,
        touched_paths=touched_paths,
        diff_text=diff_text,
        stdout_text=_read_artifact_text(db, execution.stdout_artifact_id),
        stderr_text=_read_artifact_text(db, execution.stderr_artifact_id),
        settings=settings,
    )

    failure_rows_in: list[dict] = []
    for af in result.analysed:
        tb_id = _store_traceback(
            db,
            settings=settings,
            task_id=task_id,
            snapshot_id=execution.snapshot_id,
            text=af.raw_traceback,
        )
        failure_rows_in.append(
            {
                "test_name": af.record["test_name"],
                "failure_type": af.record["failure_type"],
                "traceback_artifact_id": tb_id,
                "frames": af.record["frames"],
            }
        )

    created = FailureRepository(db).replace_for_execution(
        task_id, execution.id, failure_rows_in
    )
    inv_row = inv_repo.upsert(
        task_id,
        execution.id,
        failure_ids=[f.id for f in created],
        evidence=result.evidence,
        facts=result.facts,
        inferences=result.inferences,
        classification=result.classification,
        failures=result.failure_records,
        summary=result.summary,
    )

    TaskStepRepository(db).append(
        task_id=task_id, state=TaskState.INVESTIGATING.value, agent="debugging"
    )
    TaskRepository(db).set_state(task_id, TaskState.INVESTIGATING.value)
    jobs.mark_succeeded(job.id)

    return _to_schema(inv_row, execution.id)
