"""Job read + cancel service (Phase 21)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.job import JobState, JobType
from app.orchestration.errors import JobNotCancellableError, JobNotFoundError
from app.repository.jobs import JobRepository
from app.schemas.job import JobList, JobView
from app.services import tasks as tasks_service

_INACTIVE = (
    JobState.SUCCEEDED.value,
    JobState.FAILED.value,
    JobState.CANCELLED.value,
)


def _view(row) -> JobView:
    return JobView.model_validate(row, from_attributes=True)


def get_job(db: Session, job_id: str) -> JobView:
    row = JobRepository(db).get(job_id)
    if row is None:
        raise JobNotFoundError(f"job {job_id} not found")
    return _view(row)


def list_jobs(
    db: Session,
    *,
    state: str | None = None,
    type: str | None = None,
    task_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> JobList:
    repo = JobRepository(db)
    rows = repo.list(
        state=state, type=type, task_id=task_id, limit=limit, offset=offset
    )
    total = repo.count(state=state, type=type, task_id=task_id)
    return JobList(
        items=[_view(r) for r in rows], limit=limit, offset=offset, total=total
    )


def cancel_job(db: Session, job_id: str) -> JobView:
    repo = JobRepository(db)
    row = repo.get(job_id)
    if row is None:
        raise JobNotFoundError(f"job {job_id} not found")
    if row.state in _INACTIVE:
        raise JobNotCancellableError(
            f"job {job_id} is already {row.state}"
        )
    if row.type == JobType.RUN_TASK.value and row.task_id:
        # cancelling a pipeline run is a task-level concern (cooperative cancel)
        tasks_service.cancel_task(db, row.task_id, reason=f"job {job_id} cancelled")
        return _view(repo.get(job_id))
    return _view(repo.mark_cancelled(job_id))
