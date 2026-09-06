"""Planning service (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 17).

* ``generate_plan``          -- run the Planning agent (or the rule-based
                               fallback), persist a new plan version.
* ``get_plan``               -- read a persisted plan (latest or a version).
* ``validate_plan_for_task`` -- run the validation rules engine, record the
                               verdict on the plan row.

Job bookkeeping mirrors app.analysis.analyze.analyze_snapshot. State
transitions (``PLANNING`` / ``PLAN_VALIDATION``) are thin, unguarded
``set_state`` writes -- the guarded workflow machine is Phase 21, the same
latitude Phase 6's run/cancel took.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents import planning as planning_agent
from app.agents.errors import (
    PlanGenerationFailedError,
    PlanInputsMissingError,
    PlanNotFoundError,
    PlanTaskNotFoundError,
)
from app.ai.provider import get_provider
from app.ai.schema_guard import AIOutputInvalid
from app.core.config import Settings
from app.core.errors import AppError
from app.core.ids import new_id
from app.models.engineering_plan import EngineeringPlan as PlanRow
from app.models.job import JobType
from app.models.task import TaskState
from app.repository.code_mappings import CodeMappingRepository
from app.repository.engineering_plans import EngineeringPlanRepository
from app.repository.files import FileRepository
from app.repository.impact_analyses import ImpactAnalysisRepository
from app.repository.jobs import JobRepository
from app.repository.task_steps import TaskStepRepository
from app.repository.tasks import TaskRepository
from app.schemas.plan import EngineeringPlan, EngineeringPlanAI, PlanValidation

#: sentinel so callers can pass provider=None explicitly (the "none" provider)
#: while an omitted argument still means "resolve from settings".
_RESOLVE_FROM_SETTINGS = object()

_PLAN_FIELDS = (
    "problem_interpretation",
    "assumptions",
    "files_to_inspect",
    "files_to_modify",
    "symbols_to_modify",
    "dependencies",
    "steps",
    "test_strategy",
    "expected_behavior",
    "regression_risks",
    "rollback_strategy",
    "source",
    "confidence",
    "evidence",
)


def _row_to_ai(row: PlanRow) -> EngineeringPlanAI:
    return EngineeringPlanAI.model_validate({f: getattr(row, f) for f in _PLAN_FIELDS})


def _to_schema(row: PlanRow) -> EngineeringPlan:
    validation = (
        PlanValidation.model_validate(row.validation)
        if row.validation is not None
        else None
    )
    return EngineeringPlan(
        task_id=row.task_id,
        snapshot_id=row.snapshot_id,
        version=row.version,
        validation=validation,
        created_at=row.created_at,
        **{f: getattr(row, f) for f in _PLAN_FIELDS},
    )


def _candidate_inputs(mapping, impact) -> tuple[list[str], list[str], dict]:
    candidate_files = [c["path"] for c in mapping.candidates]
    candidate_symbols = list(impact.changed_set.get("symbols", []))
    impact_view = {
        "changed_set": impact.changed_set,
        "callers": impact.callers,
        "regression_areas": impact.regression_areas,
    }
    return candidate_files, candidate_symbols, impact_view


def generate_plan(
    db: Session, *, settings: Settings, task_id: str, provider=_RESOLVE_FROM_SETTINGS
) -> EngineeringPlan:
    task = TaskRepository(db).get(task_id)
    if task is None:
        raise PlanTaskNotFoundError(f"task {task_id} not found")

    mapping = CodeMappingRepository(db).get_by_task(task_id)
    impact = ImpactAnalysisRepository(db).get_by_task(task_id)
    if mapping is None or impact is None:
        raise PlanInputsMissingError(
            f"task {task_id} needs both a mapping (POST /analysis/map) and an "
            "impact analysis (GET /tasks/{id}/impact) before planning"
        )

    candidate_files, candidate_symbols, impact_view = _candidate_inputs(mapping, impact)
    if provider is _RESOLVE_FROM_SETTINGS:
        provider = get_provider(settings)

    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.PLAN.value,
        idempotency_key=f"plan:{task_id}:{new_id()}",
        task_id=task_id,
    )
    jobs.mark_running(job.id)
    try:
        if provider is None:
            plan_ai = planning_agent.build_fallback_plan(
                candidate_files=candidate_files, candidate_symbols=candidate_symbols
            )
        else:
            plan_ai = planning_agent.propose_plan(
                task_key=task_id,
                task_text=task.description_sanitized,
                candidate_files=candidate_files,
                candidate_symbols=candidate_symbols,
                impact=impact_view,
                provider=provider,
                timeout_s=settings.ai_planning_timeout_s,
                max_tokens=settings.ai_planning_max_tokens,
            )
    except AIOutputInvalid as exc:
        jobs.mark_failed(
            job.id, error={"code": "PLAN_GENERATION_FAILED", "message": str(exc)}
        )
        raise PlanGenerationFailedError(
            f"planning model output failed schema validation: {exc}"
        ) from exc
    except AppError as exc:
        jobs.mark_failed(job.id, error={"code": exc.code, "message": exc.message})
        raise

    row = EngineeringPlanRepository(db).create_version(
        task_id, snapshot_id=mapping.snapshot_id, plan=plan_ai.model_dump()
    )
    TaskStepRepository(db).append(
        task_id=task_id, state=TaskState.PLANNING.value, agent="planning"
    )
    TaskRepository(db).set_state(task_id, TaskState.PLANNING.value)
    jobs.mark_succeeded(job.id)
    return _to_schema(row)


def get_plan(
    db: Session, task_id: str, *, version: int | None = None
) -> EngineeringPlan:
    if TaskRepository(db).get(task_id) is None:
        raise PlanTaskNotFoundError(f"task {task_id} not found")
    repo = EngineeringPlanRepository(db)
    row = (
        repo.get_by_task_version(task_id, version)
        if version is not None
        else repo.get_latest_by_task(task_id)
    )
    if row is None:
        raise PlanNotFoundError(
            f"no plan for task {task_id}"
            + (f" version {version}" if version is not None else "")
        )
    return _to_schema(row)


def validate_plan_for_task(
    db: Session, task_id: str, *, version: int | None = None
) -> EngineeringPlan:
    if TaskRepository(db).get(task_id) is None:
        raise PlanTaskNotFoundError(f"task {task_id} not found")

    repo = EngineeringPlanRepository(db)
    row = (
        repo.get_by_task_version(task_id, version)
        if version is not None
        else repo.get_latest_by_task(task_id)
    )
    if row is None:
        raise PlanNotFoundError(f"no plan for task {task_id} to validate")

    task = TaskRepository(db).get(task_id)
    mapping = CodeMappingRepository(db).get_by_task(task_id)
    impact = ImpactAnalysisRepository(db).get_by_task(task_id)

    snapshot_paths = {
        f.path for f in FileRepository(db).list_for_snapshot(row.snapshot_id)
    }
    allowed_scope: set[str] = set()
    if mapping is not None:
        allowed_scope |= {c["path"] for c in mapping.candidates}
    if impact is not None:
        allowed_scope |= set(impact.changed_set.get("files", []))
        allowed_scope |= {
            ref.split("::", 1)[0]
            for refs in impact.blast_radius.values()
            for ref in refs
        }
    if task is not None and task.allowed_paths:
        allowed_scope |= set(task.allowed_paths)

    validation = planning_agent.validate_plan(
        _row_to_ai(row),
        snapshot_paths=snapshot_paths,
        allowed_scope=allowed_scope,
    )
    updated = repo.set_validation(
        row.id, validation=validation.model_dump(), verdict=validation.verdict
    )
    TaskStepRepository(db).append(
        task_id=task_id, state=TaskState.PLAN_VALIDATION.value, agent="planning"
    )
    TaskRepository(db).set_state(task_id, TaskState.PLAN_VALIDATION.value)
    return _to_schema(updated)
