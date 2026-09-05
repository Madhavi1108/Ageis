"""Issue -> code mapping service. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 15.

Two entry points:

* ``run_mapping`` -- compute a mapping. Task mode (``task_id``) resolves + binds
  a snapshot, persists a ``CodeMapping`` row, and returns it. Stateless mode
  (``snapshot_id`` + ``issue_text``) computes and returns without persisting --
  useful for the skeleton / debugging.
* ``get_mapping`` -- read back the persisted mapping for a task.

Job bookkeeping mirrors ``app.analysis.analyze.analyze_snapshot``: a
``Job(type=MAP)`` row is created, marked RUNNING, then SUCCEEDED / FAILED.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.analysis.mapping import mapper
from app.analysis.mapping.errors import (
    MappingNotFoundError,
    MappingSnapshotNotReadyError,
    MappingTaskNotFoundError,
)
from app.core.config import Settings
from app.core.errors import AppError
from app.core.ids import new_id
from app.models.job import JobType
from app.models.snapshot import SnapshotStatus
from app.repository.analyses import AnalysisRepository
from app.repository.code_mappings import CodeMappingRepository
from app.repository.jobs import JobRepository
from app.repository.snapshots import SnapshotRepository
from app.repository.tasks import TaskRepository
from app.schemas.mapping import IssueCodeMapping, MappingCandidate

_ANALYSABLE = (
    SnapshotStatus.READY.value,
    SnapshotStatus.PARTIALLY_SUPPORTED.value,
)


def _resolve_snapshot_for_task(db: Session, task) -> str:
    if task.snapshot_id is not None:
        snap = SnapshotRepository(db).get(task.snapshot_id)
        if snap is None or snap.status not in _ANALYSABLE:
            raise MappingSnapshotNotReadyError(
                f"task {task.id} is bound to snapshot {task.snapshot_id}, "
                "which is not ready for mapping"
            )
        return task.snapshot_id

    snapshots = SnapshotRepository(db).list_for_repository(task.repository_id)
    for snap in snapshots:  # newest first
        if snap.status in _ANALYSABLE:
            TaskRepository(db).set_snapshot_id(task.id, snap.id)
            return snap.id
    raise MappingSnapshotNotReadyError(
        f"repository {task.repository_id} has no analysable snapshot; "
        "ingest and analyse it before mapping"
    )


def _require_analysis(db: Session, snapshot_id: str) -> None:
    if AnalysisRepository(db).get_by_snapshot(snapshot_id) is None:
        raise MappingSnapshotNotReadyError(
            f"snapshot {snapshot_id} has not been analysed yet "
            "(POST .../analysis first)"
        )


def _to_schema(computation, *, task_id: str | None, created_at) -> IssueCodeMapping:
    return IssueCodeMapping(
        task_id=task_id,
        snapshot_id=computation.snapshot_id,
        candidates=computation.candidates,
        related_tests=computation.related_tests,
        dependencies=computation.dependencies,
        overall_confidence=computation.overall_confidence,
        semantic_available=computation.semantic_available,
        model_version=computation.model_version,
        created_at=created_at,
    )


def run_mapping(
    db: Session,
    *,
    settings: Settings,
    task_id: str | None = None,
    snapshot_id: str | None = None,
    issue_text: str | None = None,
    top_k: int | None = None,
) -> IssueCodeMapping:
    k = top_k or settings.mapping_top_k

    if task_id is not None:
        task = TaskRepository(db).get(task_id)
        if task is None:
            raise MappingTaskNotFoundError(f"task {task_id} not found")
        resolved_snapshot = _resolve_snapshot_for_task(db, task)
        text = task.description_sanitized
    else:
        assert snapshot_id is not None and issue_text is not None
        snap = SnapshotRepository(db).get(snapshot_id)
        if snap is None or snap.status not in _ANALYSABLE:
            raise MappingSnapshotNotReadyError(
                f"snapshot {snapshot_id} not found or not ready for mapping"
            )
        resolved_snapshot = snapshot_id
        text = issue_text

    _require_analysis(db, resolved_snapshot)

    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.MAP.value,
        idempotency_key=f"map:{resolved_snapshot}:{new_id()}",
        task_id=task_id,
    )
    jobs.mark_running(job.id)
    try:
        computation = mapper.map_issue(
            db,
            snapshot_id=resolved_snapshot,
            issue_text=text,
            settings=settings,
            top_k=k,
        )
    except AppError as exc:
        jobs.mark_failed(job.id, error={"code": exc.code, "message": exc.message})
        raise

    if task_id is not None:
        row = CodeMappingRepository(db).upsert(
            task_id,
            snapshot_id=computation.snapshot_id,
            candidates=[c.model_dump() for c in computation.candidates],
            related_tests=computation.related_tests,
            dependencies=computation.dependencies,
            overall_confidence=computation.overall_confidence,
            semantic_available=computation.semantic_available,
            model_version=computation.model_version,
        )
        jobs.mark_succeeded(job.id)
        return _to_schema(computation, task_id=task_id, created_at=row.created_at)

    jobs.mark_succeeded(job.id)
    return _to_schema(computation, task_id=None, created_at=datetime.now(timezone.utc))


def get_mapping(db: Session, task_id: str) -> IssueCodeMapping:
    if TaskRepository(db).get(task_id) is None:
        raise MappingTaskNotFoundError(f"task {task_id} not found")
    row = CodeMappingRepository(db).get_by_task(task_id)
    if row is None:
        raise MappingNotFoundError(
            f"no mapping computed yet for task {task_id} (POST /analysis/map)"
        )
    return IssueCodeMapping(
        task_id=row.task_id,
        snapshot_id=row.snapshot_id,
        candidates=[MappingCandidate(**c) for c in row.candidates],
        related_tests=row.related_tests,
        dependencies=row.dependencies,
        overall_confidence=row.overall_confidence,
        semantic_available=row.semantic_available,
        model_version=row.model_version,
        created_at=row.created_at,
    )
