"""Risk & Confidence Engine service (Phase 17,
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 25).

* ``get_or_score``  -- PCS + CRS for a task's latest patch, plus the
  Task-Specific Risk Profile. Computes both together (they share the signal
  pass), persists one ``risk_assessment`` row, returns both projections.
* ``get_or_health`` -- the Repository Health Profile for a repository's newest
  analysed snapshot.

Deterministic, no AI. Cache-unless-``refresh``; ``Job`` bookkeeping mirrors
``app.services.review``. No task-state transition -- the workflow machine has
no scoring state (the next named state is ``VERIFYING`` in Phase 18).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.ids import new_id
from app.models.job import JobType
from app.repository.analyses import AnalysisRepository
from app.repository.impact_analyses import ImpactAnalysisRepository
from app.repository.implementations import ImplementationRepository
from app.repository.jobs import JobRepository
from app.repository.repositories import RepositoryRepository
from app.repository.scoring import (
    RepositoryHealthRepository,
    RiskAssessmentRepository,
)
from app.repository.snapshots import SnapshotRepository
from app.repository.tasks import TaskRepository
from app.schemas.scoring import (
    PatchConfidence,
    PatchRiskAssessment,
    RepositoryHealthProfile,
    SignalContribution,
)
from app.scoring import confidence as confidence_mod
from app.scoring import risk as risk_mod
from app.scoring.repo_health import RHPResult, compute_rhp
from app.scoring._signal import Contribution, ScoreResult
from app.scoring.errors import (
    ScoringAnalysisMissingError,
    ScoringImpactMissingError,
    ScoringImplementationMissingError,
    ScoringRepositoryNotFoundError,
    ScoringTaskNotFoundError,
)
from app.scoring.model_registry import SCORING_MODEL_VERSION
from app.scoring.signals import collect_patch_signals


# --------------------------------------------------------------------------- #
# projection helpers
# --------------------------------------------------------------------------- #


def _contrib_schema(c: Contribution) -> SignalContribution:
    return SignalContribution(
        name=c.name,
        raw=c.raw,
        normalized=round(c.normalized, 6),
        weight=c.weight,
        contribution=round(c.contribution, 6),
        basis=c.basis,
        unavailable_reason=c.unavailable_reason,
        evidence=list(c.evidence),
    )


def _rhp_schema(
    rhp: RHPResult,
    *,
    repository_id: str,
    snapshot_id: str,
    created_at: datetime,
    scope: str,
) -> RepositoryHealthProfile:
    return RepositoryHealthProfile(
        repository_id=repository_id,
        snapshot_id=snapshot_id,
        value=rhp.value,
        classification=rhp.classification,
        subscores=[_contrib_schema(c) for c in rhp.subscores],
        risky_modules=rhp.risky_modules,
        scope=scope,
        model_version=rhp.model_version,
        created_at=created_at,
    )


def _pcs_schema(
    task_id: str,
    version: int,
    pcs: ScoreResult,
    evidence_refs: list,
    created_at: datetime,
) -> PatchConfidence:
    return PatchConfidence(
        task_id=task_id,
        implementation_version=version,
        value=pcs.value,
        classification=pcs.classification,
        pcs_raw=pcs.raw,
        security_gate=pcs.security_gate,
        hard_gate=pcs.hard_gate,
        per_signal_contributions=[_contrib_schema(c) for c in pcs.contributions],
        overall_confidence=pcs.overall_confidence,
        evidence_refs=list(evidence_refs),
        model_version=pcs.model_version,
        created_at=created_at,
    )


def _crs_schema(
    task_id: str,
    version: int,
    crs: ScoreResult,
    task_risk_profile: RepositoryHealthProfile,
    evidence_refs: list,
    created_at: datetime,
) -> PatchRiskAssessment:
    return PatchRiskAssessment(
        task_id=task_id,
        implementation_version=version,
        value=crs.value,
        classification=crs.classification,
        crs_raw=crs.raw,
        per_signal_contributions=[_contrib_schema(c) for c in crs.contributions],
        overall_confidence=crs.overall_confidence,
        task_risk_profile=task_risk_profile,
        evidence_refs=list(evidence_refs),
        model_version=crs.model_version,
        created_at=created_at,
    )


def _project_row(row) -> tuple[PatchConfidence, PatchRiskAssessment]:
    pcs = PatchConfidence.model_validate(
        {**row.pcs_breakdown, "created_at": row.created_at}
    )
    crs = PatchRiskAssessment.model_validate(
        {**row.crs_breakdown, "created_at": row.created_at}
    )
    return pcs, crs


# --------------------------------------------------------------------------- #
# PCS + CRS
# --------------------------------------------------------------------------- #


def get_or_score(
    db: Session, *, settings: Settings, task_id: str, refresh: bool = False
) -> tuple[PatchConfidence, PatchRiskAssessment]:
    if TaskRepository(db).get(task_id) is None:
        raise ScoringTaskNotFoundError(f"task {task_id} not found")

    impl = ImplementationRepository(db).get_latest_by_task(task_id)
    if impl is None:
        raise ScoringImplementationMissingError(
            f"task {task_id} has no implementation to score "
            f"(POST /tasks/{{id}}/changes)"
        )
    if ImpactAnalysisRepository(db).get_by_task(task_id) is None:
        raise ScoringImpactMissingError(
            f"task {task_id} has no impact analysis "
            f"(GET /tasks/{{id}}/impact) -- required for the Change Risk Score"
        )

    repo = RiskAssessmentRepository(db)
    existing = repo.get_by_task(task_id)
    if existing is not None and not refresh:
        return _project_row(existing)

    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.SCORE.value,
        idempotency_key=f"score:{task_id}:{new_id()}",
        task_id=task_id,
    )
    jobs.mark_running(job.id)
    try:
        inputs = collect_patch_signals(db, task_id=task_id, settings=settings)
        pcs = confidence_mod.compute_pcs(
            inputs.pcs_signals,
            security_gate=inputs.security_gate,
            hard_gates=inputs.hard_gates,
        )
        crs = risk_mod.compute_crs(inputs.crs_signals)
        rhp = compute_rhp(
            db,
            inputs.snapshot_id,
            repository_id=_repo_id_for_snapshot(db, inputs.snapshot_id),
            restrict_to=inputs.impact_files or None,
        )
        now = datetime.now(timezone.utc)
        task_profile = _rhp_schema(
            rhp,
            repository_id=_repo_id_for_snapshot(db, inputs.snapshot_id),
            snapshot_id=inputs.snapshot_id,
            created_at=now,
            scope="task",
        )
        pcs_schema = _pcs_schema(
            task_id, inputs.implementation_version, pcs, inputs.evidence_refs, now
        )
        crs_schema = _crs_schema(
            task_id,
            inputs.implementation_version,
            crs,
            task_profile,
            inputs.evidence_refs,
            now,
        )
    except Exception as exc:  # pragma: no cover - defensive job bookkeeping
        jobs.mark_failed(job.id, error={"code": "SCORING_FAILED", "message": str(exc)})
        raise

    row = repo.upsert(
        task_id,
        snapshot_id=inputs.snapshot_id,
        implementation_version=inputs.implementation_version,
        patch_id=inputs.patch_id,
        pcs_value=pcs.value,
        pcs_classification=pcs.classification,
        pcs_breakdown=pcs_schema.model_dump(mode="json", exclude={"created_at"}),
        crs_value=crs.value,
        crs_classification=crs.classification,
        crs_breakdown=crs_schema.model_dump(mode="json", exclude={"created_at"}),
        task_risk_profile=task_profile.model_dump(mode="json", exclude={"created_at"}),
        hard_gate=pcs.hard_gate,
        model_version=SCORING_MODEL_VERSION,
    )
    jobs.mark_succeeded(job.id)
    return _project_row(row)


def _repo_id_for_snapshot(db: Session, snapshot_id: str) -> str:
    snap = SnapshotRepository(db).get(snapshot_id)
    assert snap is not None
    return snap.repository_id


# --------------------------------------------------------------------------- #
# RHP
# --------------------------------------------------------------------------- #


def get_or_health(
    db: Session, *, settings: Settings, repository_id: str, refresh: bool = False
) -> RepositoryHealthProfile:
    if RepositoryRepository(db).get(repository_id) is None:
        raise ScoringRepositoryNotFoundError(
            f"repository {repository_id} not found"
        )

    analyses = AnalysisRepository(db)
    snapshot_id: str | None = None
    for snap in SnapshotRepository(db).list_for_repository(repository_id):
        if analyses.get_by_snapshot(snap.id) is not None:
            snapshot_id = snap.id
            break
    if snapshot_id is None:
        raise ScoringAnalysisMissingError(
            f"repository {repository_id} has no analysed snapshot "
            f"(POST /repositories/{{id}}/snapshots/{{sid}}/analysis)"
        )

    repo = RepositoryHealthRepository(db)
    existing = repo.get_by_snapshot(snapshot_id)
    if existing is not None and not refresh:
        return _rhp_from_row(existing)

    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.SCORE.value,
        idempotency_key=f"health:{repository_id}:{new_id()}",
        task_id=None,
    )
    jobs.mark_running(job.id)
    try:
        rhp = compute_rhp(db, snapshot_id, repository_id=repository_id)
    except Exception as exc:  # pragma: no cover - defensive job bookkeeping
        jobs.mark_failed(job.id, error={"code": "SCORING_FAILED", "message": str(exc)})
        raise

    row = repo.upsert(
        snapshot_id,
        repository_id=repository_id,
        rhp_value=rhp.value,
        rhp_classification=rhp.classification,
        subscores=[_contrib_schema(c).model_dump(mode="json") for c in rhp.subscores],
        risky_modules=rhp.risky_modules,
        model_version=rhp.model_version,
    )
    jobs.mark_succeeded(job.id)
    return _rhp_from_row(row)


def _rhp_from_row(row) -> RepositoryHealthProfile:
    return RepositoryHealthProfile(
        repository_id=row.repository_id,
        snapshot_id=row.snapshot_id,
        value=row.rhp_value,
        classification=row.rhp_classification,
        subscores=[SignalContribution.model_validate(s) for s in row.subscores],
        risky_modules=row.risky_modules,
        scope="repository",
        model_version=row.model_version,
        created_at=row.created_at,
    )
