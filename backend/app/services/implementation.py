"""Implementation service (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 18).

* ``generate_implementation`` -- apply the latest APPROVED EngineeringPlan to
  a throwaway RW workspace, produce a real unified diff, persist
  Implementation + Patch + Artifact, transition the task to IMPLEMENTING.
* ``get_implementation``      -- read a persisted implementation (latest or a
  version) plus its diff text.

Job bookkeeping mirrors app.services.planning.generate_plan. State transition
(``IMPLEMENTING``) is a thin, unguarded ``set_state`` write, same latitude
every prior phase took (the guarded workflow machine is Phase 21).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.schema_guard import AIOutputInvalid
from app.core.config import Settings
from app.core.ids import new_id
from app.implementation import agent as implementation_agent
from app.implementation.errors import (
    ImplementationFailedError,
    ImplementationNotFoundError,
    ImplementationPlanNotApprovedError,
    ImplementationTaskNotFoundError,
)
from app.implementation.workspace_rw import clone_rw
from app.ingestion.workspace import workspace_dir
from app.models.artifact import ArtifactKind, ArtifactRetention, ArtifactStoreKind
from app.models.implementation import Implementation as ImplementationRow
from app.models.job import JobType
from app.models.task import TaskState
from app.repository.artifacts import ArtifactRepository
from app.repository.code_mappings import CodeMappingRepository
from app.repository.engineering_plans import EngineeringPlanRepository
from app.repository.files import FileRepository
from app.repository.impact_analyses import ImpactAnalysisRepository
from app.repository.implementations import ImplementationRepository
from app.repository.jobs import JobRepository
from app.repository.patches import PatchRepository
from app.repository.task_steps import TaskStepRepository
from app.repository.tasks import TaskRepository
from app.schemas.implementation import EditOp, ImplementationResult, PatchSummary

#: sentinel so callers can pass provider=None explicitly (the "none" provider)
#: while an omitted argument still means "resolve from settings".
_RESOLVE_FROM_SETTINGS = object()


def _allowed_scope(db: Session, task_id: str, plan) -> set[str]:
    """Same union planning's own validator builds: mapping candidates, impact
    changed-set/blast-radius files, and the task's explicit allowlist -- plus
    the plan's own declared ``files_to_modify`` (the actual thing being
    implemented)."""
    scope: set[str] = set(plan.files_to_modify)
    mapping = CodeMappingRepository(db).get_by_task(task_id)
    impact = ImpactAnalysisRepository(db).get_by_task(task_id)
    if mapping is not None:
        scope |= {c["path"] for c in mapping.candidates}
    if impact is not None:
        scope |= set(impact.changed_set.get("files", []))
        scope |= {
            ref.split("::", 1)[0]
            for refs in impact.blast_radius.values()
            for ref in refs
        }
    task = TaskRepository(db).get(task_id)
    if task is not None and task.allowed_paths:
        scope |= set(task.allowed_paths)
    return scope


def _traceability(applied_ops: list[EditOp]) -> dict[str, list[str]]:
    trace: dict[str, list[str]] = {}
    for op in applied_ops:
        trace.setdefault(op.plan_step_id, [])
        if op.path not in trace[op.plan_step_id]:
            trace[op.plan_step_id].append(op.path)
    return trace


def _row_to_schema(row: ImplementationRow, *, patch, diff_text: str) -> ImplementationResult:
    return ImplementationResult(
        task_id=row.task_id,
        snapshot_id=row.snapshot_id,
        version=row.version,
        edit_ops=[EditOp.model_validate(op) for op in row.edit_ops],
        scope_violations=row.scope_violations,
        traceability=row.traceability,
        source=row.source,
        patch=PatchSummary(
            diff_text=diff_text,
            touched_paths=patch.touched_paths,
            diff_size=patch.diff_size,
        ),
        created_at=row.created_at,
    )


def generate_implementation(
    db: Session,
    *,
    settings: Settings,
    task_id: str,
    provider=_RESOLVE_FROM_SETTINGS,
) -> ImplementationResult:
    task = TaskRepository(db).get(task_id)
    if task is None:
        raise ImplementationTaskNotFoundError(f"task {task_id} not found")

    plan_row = EngineeringPlanRepository(db).get_latest_by_task(task_id)
    if plan_row is None or plan_row.validation_verdict != "APPROVED":
        raise ImplementationPlanNotApprovedError(
            f"task {task_id} needs an APPROVED plan (POST /tasks/{{id}}/plan then "
            "POST /tasks/{id}/plan/validate) before implementation can run"
        )

    if provider is _RESOLVE_FROM_SETTINGS:
        from app.ai.provider import get_provider

        provider = get_provider(settings)
    if provider is None:
        raise ImplementationFailedError(
            "no AI provider configured (ai_provider='none'); real code edits "
            "cannot be fabricated by a deterministic fallback"
        )

    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.IMPLEMENT.value,
        idempotency_key=f"implement:{task_id}:{new_id()}",
        task_id=task_id,
    )
    jobs.mark_running(job.id)

    source_workspace = workspace_dir(plan_row.snapshot_id, settings)
    ws = clone_rw(plan_row.snapshot_id, source_workspace)
    try:
        allowed_scope = _allowed_scope(db, task_id, plan_row)
        try:
            edit_ops = implementation_agent.propose_edit_ops(
                task_key=task_id,
                plan_steps=plan_row.steps,
                files_to_modify=plan_row.files_to_modify,
                symbols_to_modify=plan_row.symbols_to_modify,
                problem_interpretation=plan_row.problem_interpretation,
                provider=provider,
                timeout_s=settings.ai_implementation_timeout_s,
                max_tokens=settings.ai_implementation_max_tokens,
            )
        except AIOutputInvalid as exc:
            jobs.mark_failed(
                job.id, error={"code": "IMPLEMENTATION_FAILED", "message": str(exc)}
            )
            raise ImplementationFailedError(
                f"implementation model output failed schema validation: {exc}"
            ) from exc

        if len(edit_ops) > settings.implementation_max_edit_ops:
            jobs.mark_failed(
                job.id,
                error={
                    "code": "IMPLEMENTATION_FAILED",
                    "message": f"{len(edit_ops)} edit ops exceeds the configured cap",
                },
            )
            raise ImplementationFailedError(
                f"model proposed {len(edit_ops)} edit ops, more than the "
                f"configured cap of {settings.implementation_max_edit_ops}"
            )

        result = implementation_agent.apply_and_diff(
            ws, source_workspace, edit_ops, allowed_scope=allowed_scope
        )
        if not result.applied_ops:
            jobs.mark_failed(
                job.id,
                error={
                    "code": "IMPLEMENTATION_FAILED",
                    "message": result.failed_op_error or "no edit op applied",
                },
            )
            raise ImplementationFailedError(
                f"no edit op could be applied: {result.failed_op_error}"
            )

        traceability = _traceability(result.applied_ops)
        impl_row = ImplementationRepository(db).create_version(
            task_id,
            snapshot_id=plan_row.snapshot_id,
            plan_id=plan_row.id,
            edit_ops=[op.model_dump() for op in result.applied_ops],
            scope_violations=sorted(result.scope_violations),
            traceability=traceability,
            source="AI",
        )

        artifacts_root = Path(settings.artifacts_root)
        patches_dir = artifacts_root / "patches"
        patches_dir.mkdir(parents=True, exist_ok=True)
        diff_path = patches_dir / f"{impl_row.id}.diff"
        diff_bytes = result.diff_text.encode("utf-8")
        diff_path.write_bytes(diff_bytes)

        artifact = ArtifactRepository(db).create(
            kind=ArtifactKind.DIFF.value,
            store=ArtifactStoreKind.FS.value,
            uri=str(diff_path),
            retention=ArtifactRetention.RETAINED.value,
            snapshot_id=plan_row.snapshot_id,
            task_id=task_id,
            sha256=hashlib.sha256(diff_bytes).hexdigest(),
            size_bytes=len(diff_bytes),
            content_type="text/x-diff",
        )
        patch = PatchRepository(db).create(
            implementation_id=impl_row.id,
            artifact_id=artifact.id,
            touched_paths=sorted(result.touched),
            diff_size=len(diff_bytes),
        )

        TaskStepRepository(db).append(
            task_id=task_id, state=TaskState.IMPLEMENTING.value, agent="implementation"
        )
        TaskRepository(db).set_state(task_id, TaskState.IMPLEMENTING.value)
        jobs.mark_succeeded(job.id)
        return _row_to_schema(impl_row, patch=patch, diff_text=result.diff_text)
    finally:
        ws.cleanup()


def get_implementation(
    db: Session, task_id: str, *, version: int | None = None
) -> ImplementationResult:
    if TaskRepository(db).get(task_id) is None:
        raise ImplementationTaskNotFoundError(f"task {task_id} not found")

    repo = ImplementationRepository(db)
    row = (
        repo.get_by_task_version(task_id, version)
        if version is not None
        else repo.get_latest_by_task(task_id)
    )
    if row is None:
        raise ImplementationNotFoundError(
            f"no implementation for task {task_id}"
            + (f" version {version}" if version is not None else "")
        )

    patch = PatchRepository(db).get_by_implementation(row.id)
    assert patch is not None
    artifact = ArtifactRepository(db).get(patch.artifact_id)
    assert artifact is not None
    diff_text = Path(artifact.uri).read_text(encoding="utf-8")
    return _row_to_schema(row, patch=patch, diff_text=diff_text)
