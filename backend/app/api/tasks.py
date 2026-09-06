"""Task / issue ingestion API. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 14.

Routes: create / get / list (with filtering + pagination), run, cancel, timeline.
All normalization, inference, dedupe and state logic lives in
app/services/tasks.py; these handlers are thin.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.deps import get_ai_provider
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.impact import ImpactAnalysis
from app.schemas.implementation import ImplementationResult
from app.schemas.mapping import IssueCodeMapping
from app.schemas.plan import EngineeringPlan
from app.schemas.task import (
    Task,
    TaskCancelRequest,
    TaskCreate,
    TaskCreateResponse,
    TaskList,
    TaskTimeline,
)
from app.schemas.testing import TestGeneration
from app.services import impact as impact_service
from app.services import implementation as implementation_service
from app.services import mapping as mapping_service
from app.services import planning as planning_service
from app.services import tasks as tasks_service
from app.services import testing as testing_service

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


@router.get("/{task_id}/impact", response_model=ImpactAnalysis)
def get_task_impact(
    task_id: str,
    refresh: bool = False,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ImpactAnalysis:
    """The impact analysis for this task (Phase 8): changed set, blast radius,
    callers, related tests, public API, config/DB refs, regression areas, and
    the CRS risk-signal bundle. Computed and persisted on first access (or with
    ``?refresh=true``); requires the Phase 7 mapping to exist."""
    return impact_service.get_or_compute_impact(
        db, settings=settings, task_id=task_id, refresh=refresh
    )


@router.post("/{task_id}/plan", status_code=201, response_model=EngineeringPlan)
def create_task_plan(
    task_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    provider=Depends(get_ai_provider),
) -> EngineeringPlan:
    """Generate + persist a new EngineeringPlan version for this task (Phase 9).
    Requires the Phase 7 mapping and the Phase 8 impact analysis to exist."""
    return planning_service.generate_plan(
        db, settings=settings, task_id=task_id, provider=provider
    )


@router.get("/{task_id}/plan", response_model=EngineeringPlan)
def get_task_plan(
    task_id: str,
    version: int | None = None,
    db: Session = Depends(get_db),
) -> EngineeringPlan:
    """The latest persisted plan for this task (or a specific ``?version=``)."""
    return planning_service.get_plan(db, task_id, version=version)


@router.post("/{task_id}/plan/validate", response_model=EngineeringPlan)
def validate_task_plan(
    task_id: str,
    version: int | None = None,
    db: Session = Depends(get_db),
) -> EngineeringPlan:
    """Run the plan-validation rules engine and record the verdict
    (``APPROVED`` / ``REVISE`` / ``REJECTED``) on the plan row."""
    return planning_service.validate_plan_for_task(db, task_id, version=version)


@router.post(
    "/{task_id}/changes", status_code=201, response_model=ImplementationResult
)
def create_task_changes(
    task_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    provider=Depends(get_ai_provider),
) -> ImplementationResult:
    """Apply the latest APPROVED EngineeringPlan to a throwaway workspace and
    persist a new Implementation + real unified diff (Phase 10). Requires
    ``POST /tasks/{id}/plan/validate`` to have returned ``APPROVED``."""
    return implementation_service.generate_implementation(
        db, settings=settings, task_id=task_id, provider=provider
    )


@router.get("/{task_id}/changes", response_model=ImplementationResult)
def get_task_changes(
    task_id: str,
    version: int | None = None,
    db: Session = Depends(get_db),
) -> ImplementationResult:
    """The latest persisted implementation + diff for this task (or a
    specific ``?version=``)."""
    return implementation_service.get_implementation(db, task_id, version=version)


@router.post("/{task_id}/tests", status_code=201, response_model=TestGeneration)
def create_task_tests(
    task_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    provider=Depends(get_ai_provider),
) -> TestGeneration:
    """Generate + persist a new batch of tests for this task's latest
    Implementation (Phase 11). Requires ``POST /tasks/{id}/changes`` to have
    produced an Implementation."""
    return testing_service.generate_tests(
        db, settings=settings, task_id=task_id, provider=provider
    )


@router.get("/{task_id}/tests", response_model=TestGeneration)
def get_task_tests(
    task_id: str,
    version: int | None = None,
    db: Session = Depends(get_db),
) -> TestGeneration:
    """The latest persisted test-generation batch for this task (or a
    specific ``?version=``)."""
    return testing_service.get_tests(db, task_id, version=version)
