"""Code-review service (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 24).

``get_or_review`` reconstructs the latest patch into a throwaway workspace,
runs the static analysers + custom AST rules + the AI reviewer, aggregates the
findings, and persists a ``Review`` (aggregate) + ``ReviewFinding`` rows.
Computed and persisted on first access; ``refresh=True`` recomputes. Not
Docker-gated -- nothing here executes repository code.
"""

from __future__ import annotations

from collections import Counter

from sqlalchemy.orm import Session

from app.ai.provider import get_provider
from app.core.config import Settings
from app.core.ids import new_id
from app.implementation.patcher import touched_paths, unified_diff
from app.implementation.workspace_rw import clone_rw
from app.ingestion.workspace import workspace_dir
from app.models.job import JobType
from app.models.task import TaskState
from app.repository.dependencies import DependencyRepository
from app.repository.implementations import ImplementationRepository
from app.repository.jobs import JobRepository
from app.repository.reviews import ReviewFindingRepository, ReviewRepository
from app.repository.task_steps import TaskStepRepository
from app.repository.tasks import TaskRepository
from app.review import aggregate as aggregate_mod
from app.review import rules as rules_mod
from app.review import static_checks
from app.review.agent import ai_review
from app.review.errors import (
    ReviewImplementationMissingError,
    ReviewTaskNotFoundError,
)
from app.schemas.review import ReviewFinding, ReviewReport
from app.services.execution import _reconstruct_implementation
from app.services.repair import _allowed_files

_RESOLVE_FROM_SETTINGS = object()


def _report_from_row(row) -> ReviewReport:
    return ReviewReport(
        task_id=row.task_id,
        implementation_version=row.implementation_version,
        findings=[ReviewFinding.model_validate(f) for f in row.findings],
        counts_by_severity=row.counts.get("severity", {}),
        counts_by_category=row.counts.get("category", {}),
        blocking=row.blocking,
        static_tools_run=row.static_tools_run,
        policy_gaps=row.policy_gaps,
        created_at=row.created_at,
    )


def get_or_review(
    db: Session,
    *,
    settings: Settings,
    task_id: str,
    provider=_RESOLVE_FROM_SETTINGS,
    refresh: bool = False,
) -> ReviewReport:
    if TaskRepository(db).get(task_id) is None:
        raise ReviewTaskNotFoundError(f"task {task_id} not found")

    impl = ImplementationRepository(db).get_latest_by_task(task_id)
    if impl is None:
        raise ReviewImplementationMissingError(
            f"task {task_id} has no implementation to review (POST /tasks/{{id}}/changes)"
        )

    repo = ReviewRepository(db)
    existing = repo.get_by_task(task_id)
    if existing is not None and not refresh:
        return _report_from_row(existing)

    if provider is _RESOLVE_FROM_SETTINGS:
        provider = get_provider(settings)

    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.REVIEW.value,
        idempotency_key=f"review:{task_id}:{new_id()}",
        task_id=task_id,
    )
    jobs.mark_running(job.id)

    source_ws = workspace_dir(impl.snapshot_id, settings)
    ws = clone_rw(impl.snapshot_id, source_ws)
    try:
        _reconstruct_implementation(ws, impl)
        diff_text = unified_diff(source_ws, ws)
        touched = touched_paths(source_ws, ws)
        files_src: dict[str, str] = {}
        for p in sorted(touched):
            fp = ws.path_for(p)
            if p.endswith(".py") and fp.is_file():
                files_src[p] = fp.read_text(encoding="utf-8", errors="replace")

        known_deps = {
            d.target
            for d in DependencyRepository(db).list_for_snapshot(impl.snapshot_id)
        }
        allowed_scope = set(_allowed_files(db, task_id))

        static_findings, tools_run, gaps = static_checks.run_static(
            ws.root, sorted(files_src)
        )
        rule_findings = rules_mod.run_rules(files_src, impl.edit_ops, known_deps)
        ai_findings, ai_gaps = ai_review(
            diff_text=diff_text,
            files_src=files_src,
            provider=provider,
            settings=settings,
            task_key=task_id,
        )
        gaps.extend(ai_gaps)

        raw = (
            static_findings
            + rule_findings
            + ai_findings
            + aggregate_mod.scope_findings(touched, allowed_scope)
        )
        findings = aggregate_mod.aggregate(raw)
        is_blocking = aggregate_mod.blocking(findings)
    finally:
        ws.cleanup()

    by_sev = Counter(f.severity for f in findings)
    by_cat = Counter(f.category for f in findings)
    finding_dumps = [f.model_dump() for f in findings]

    repo.upsert(
        task_id,
        snapshot_id=impl.snapshot_id,
        implementation_version=impl.version,
        findings=finding_dumps,
        static_tools_run=tools_run,
        policy_gaps=gaps,
        counts={"severity": dict(by_sev), "category": dict(by_cat)},
        blocking=is_blocking,
    )
    ReviewFindingRepository(db).replace_for_task(task_id, finding_dumps)

    TaskStepRepository(db).append(
        task_id=task_id, state=TaskState.REVIEWING.value, agent="review"
    )
    TaskRepository(db).set_state(task_id, TaskState.REVIEWING.value)
    jobs.mark_succeeded(job.id)

    return ReviewReport(
        task_id=task_id,
        implementation_version=impl.version,
        findings=findings,
        counts_by_severity=dict(by_sev),
        counts_by_category=dict(by_cat),
        blocking=is_blocking,
        static_tools_run=tools_run,
        policy_gaps=gaps,
        created_at=repo.get_by_task(task_id).created_at,
    )
