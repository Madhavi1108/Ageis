"""Job API (Phase 21, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 29).

The job system is otherwise driven inside service functions; this router
exposes it for observability + operator cancel.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import operator_required
from app.db.session import get_db
from app.schemas.job import JobList, JobView
from app.services import jobs as jobs_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobList)
def list_jobs(
    state: str | None = None,
    type: str | None = None,
    task_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> JobList:
    """Jobs, newest first, filtered by ``state`` / ``type`` / ``task_id``, with
    ``limit`` / ``offset`` / ``total`` pagination."""
    return jobs_service.list_jobs(
        db, state=state, type=type, task_id=task_id, limit=limit, offset=offset
    )


@router.get("/{job_id}", response_model=JobView)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JobView:
    return jobs_service.get_job(db, job_id)


@router.post(
    "/{job_id}/cancel",
    response_model=JobView,
    dependencies=[operator_required],
)
def cancel_job(job_id: str, db: Session = Depends(get_db)) -> JobView:
    """Cancel a ``PENDING`` / ``QUEUED`` / ``RUNNING`` job. Cancelling a
    ``RUN_TASK`` job cooperatively cancels its task. 409 if already finished."""
    return jobs_service.cancel_job(db, job_id)
