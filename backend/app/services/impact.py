"""Impact analysis service. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 16.

``get_or_compute_impact`` is the single entry point behind
``GET /tasks/{id}/impact``: it returns the persisted ``impact_analysis`` row,
computing and storing it on first access (or when ``refresh`` is set). Impact is
fully derived from already-persisted data (the Phase 7 mapping + the Phase 5
graph), so a lazy GET is sufficient -- no separate compute endpoint.

Job bookkeeping mirrors app.analysis.analyze.analyze_snapshot: a
``Job(type=IMPACT)`` row is created, marked RUNNING, then SUCCEEDED / FAILED.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.analysis import impact as impact_engine
from app.analysis.errors import ImpactMappingMissingError, ImpactTaskNotFoundError
from app.core.config import Settings
from app.core.errors import AppError
from app.core.ids import new_id
from app.models.impact_analysis import ImpactAnalysis as ImpactRow
from app.models.job import JobType
from app.repository.code_mappings import CodeMappingRepository
from app.repository.impact_analyses import ImpactAnalysisRepository
from app.repository.jobs import JobRepository
from app.repository.tasks import TaskRepository
from app.schemas.impact import ImpactAnalysis


def _render_report(row: ImpactRow) -> str:
    cs = row.changed_set or {"files": [], "symbols": []}
    lines: list[str] = []
    files = cs.get("files", [])
    lines.append(
        f"Impact analysis for {len(files)} changed file(s): "
        + (", ".join(files) or "(none)")
    )
    if cs.get("symbols"):
        lines.append("Changed symbols: " + ", ".join(cs["symbols"]))

    if row.callers:
        for entry in row.callers:
            refs = ", ".join(c["ref"] for c in entry["callers"]) or "(none)"
            lines.append(f"Callers of {entry['symbol']}: {refs}")
    else:
        lines.append("Callers: none")

    lines.append("Related tests: " + (", ".join(row.related_tests) or "none"))
    pub = ", ".join(p["symbol_id"] for p in row.public_api_touched) or "none"
    lines.append(f"Public API touched: {pub}")

    total_blast = sum(len(v) for v in (row.blast_radius or {}).values())
    lines.append(
        f"Blast radius: {total_blast} node(s) across "
        f"{len(row.blast_radius or {})} hop level(s)"
    )

    avail = {
        k: v["normalized"]
        for k, v in (row.risk_signal_bundle or {}).items()
        if v.get("value") is not None
    }
    lines.append(
        "Risk signals: " + (", ".join(f"{k}={v}" for k, v in avail.items()) or "none")
    )
    lines.append(
        f"Config refs: {len(row.config_refs)} (INFERENCE); "
        f"DB refs: {len(row.db_refs)} (INFERENCE)"
    )
    return "\n".join(lines)


def _to_schema(row: ImpactRow) -> ImpactAnalysis:
    return ImpactAnalysis(
        task_id=row.task_id,
        snapshot_id=row.snapshot_id,
        changed_set=row.changed_set,
        blast_radius=row.blast_radius,
        callers=row.callers,
        related_tests=row.related_tests,
        public_api_touched=row.public_api_touched,
        config_refs=row.config_refs,
        db_refs=row.db_refs,
        regression_areas=row.regression_areas,
        risk_signal_bundle=row.risk_signal_bundle,
        report=_render_report(row),
        created_at=row.created_at,
    )


def get_or_compute_impact(
    db: Session,
    *,
    settings: Settings,
    task_id: str,
    refresh: bool = False,
) -> ImpactAnalysis:
    if TaskRepository(db).get(task_id) is None:
        raise ImpactTaskNotFoundError(f"task {task_id} not found")

    mapping = CodeMappingRepository(db).get_by_task(task_id)
    if mapping is None:
        raise ImpactMappingMissingError(
            f"task {task_id} has no issue -> code mapping yet; "
            "POST /analysis/map first"
        )

    repo = ImpactAnalysisRepository(db)
    existing = repo.get_by_task(task_id)
    if existing is not None and not refresh:
        return _to_schema(existing)

    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.IMPACT.value,
        idempotency_key=f"impact:{task_id}:{new_id()}",
        task_id=task_id,
    )
    jobs.mark_running(job.id)
    try:
        comp = impact_engine.compute(
            db,
            snapshot_id=mapping.snapshot_id,
            mapping_candidates=mapping.candidates,
            settings=settings,
        )
    except AppError as exc:
        jobs.mark_failed(job.id, error={"code": exc.code, "message": exc.message})
        raise

    row = repo.upsert(
        task_id,
        snapshot_id=comp.snapshot_id,
        changed_set=comp.changed_set,
        blast_radius=comp.blast_radius,
        callers=comp.callers,
        related_tests=comp.related_tests,
        public_api_touched=comp.public_api_touched,
        config_refs=comp.config_refs,
        db_refs=comp.db_refs,
        regression_areas=comp.regression_areas,
        risk_signal_bundle=comp.risk_signal_bundle,
    )
    jobs.mark_succeeded(job.id)
    return _to_schema(row)
