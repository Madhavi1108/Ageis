"""Task / issue ingestion API. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 14.

Routes: create / get / list (with filtering + pagination), run, cancel, timeline.
All normalization, inference, dedupe and state logic lives in
app/services/tasks.py; these handlers are thin.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.mapping import IssueCodeMapping
from app.schemas.task import (
    Task,
    TaskCancelRequest,
    TaskCreate,
    TaskCreateResponse,
    TaskList,
    TaskTimeline,
)
from app.services import mapping as mapping_service
from app.services import tasks as tasks_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", status_code=201, response_model=TaskCreateResponse)
def create_task(
    body: TaskCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TaskCreateResponse:
    return tasks_service.create_task(db, settings=settings, payload=body)


@router.get("", response_model=TaskList)
def list_tasks(
    repository_id: str | None = None,
    state: str | None = None,
    task_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> TaskList:
    return tasks_service.list_tasks(
        db,
        repository_id=repository_id,
        state=state,
        task_type=task_type,
        limit=limit,
        offset=offset,
    )


@router.get("/{task_id}", response_model=Task)
def get_task(task_id: str, db: Session = Depends(get_db)) -> Task:
    return tasks_service.get_task(db, task_id)


@router.post("/{task_id}/run", response_model=Task)
def run_task(task_id: str, db: Session = Depends(get_db)) -> Task:
    return tasks_service.run_task(db, task_id)


@router.post("/{task_id}/cancel", response_model=Task)
def cancel_task(
    task_id: str,
    body: TaskCancelRequest | None = None,
    db: Session = Depends(get_db),
) -> Task:
    reason = body.reason if body is not None else None
    return tasks_service.cancel_task(db, task_id, reason=reason)


@router.get("/{task_id}/timeline", response_model=TaskTimeline)
def get_task_timeline(task_id: str, db: Session = Depends(get_db)) -> TaskTimeline:
    return tasks_service.build_timeline(db, task_id)


@router.get("/{task_id}/mapping", response_model=IssueCodeMapping)
def get_task_mapping(task_id: str, db: Session = Depends(get_db)) -> IssueCodeMapping:
    """The persisted issue -> code mapping for this task (Phase 7). Compute it
    first with ``POST /analysis/map`` (``{"task_id": ...}``)."""
    return mapping_service.get_mapping(db, task_id)
