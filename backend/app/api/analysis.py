"""Repository analysis API. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 12.

Nested under /repositories/{id}/snapshots/{snapshot_id}, consistent with Phase 3's
existing URL shape for snapshots.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analysis.analyze import analyze_snapshot, build_analysis_result
from app.analysis.errors import AnalysisNotFoundError, SnapshotNotFoundError
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.repository.analyses import AnalysisRepository
from app.repository.snapshots import SnapshotRepository
from app.schemas.analysis import AnalyzeRequest, RepositoryAnalysisResult

router = APIRouter(prefix="/repositories", tags=["analysis"])


def _get_snapshot_or_404(db: Session, repository_id: str, snapshot_id: str):
    snapshot = SnapshotRepository(db).get(snapshot_id)
    if snapshot is None or snapshot.repository_id != repository_id:
        raise SnapshotNotFoundError(
            f"snapshot {snapshot_id} not found for repository {repository_id}"
        )
    return snapshot


@router.post(
    "/{repository_id}/snapshots/{snapshot_id}/analysis",
    status_code=201,
    response_model=RepositoryAnalysisResult,
)
def create_analysis(
    repository_id: str,
    snapshot_id: str,
    body: AnalyzeRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RepositoryAnalysisResult:
    snapshot = _get_snapshot_or_404(db, repository_id, snapshot_id)
    return analyze_snapshot(db, snapshot=snapshot, settings=settings, force=body.force)


@router.get(
    "/{repository_id}/snapshots/{snapshot_id}/analysis",
    response_model=RepositoryAnalysisResult,
)
def get_analysis(
    repository_id: str, snapshot_id: str, db: Session = Depends(get_db)
) -> RepositoryAnalysisResult:
    _get_snapshot_or_404(db, repository_id, snapshot_id)
    analysis = AnalysisRepository(db).get_by_snapshot(snapshot_id)
    if analysis is None:
        raise AnalysisNotFoundError(
            f"no analysis recorded yet for snapshot {snapshot_id}"
        )
    # job_id isn't tracked on the RepositoryAnalysis row itself (it belongs to the Job
    # that produced it); GET has no fresh job to report, so this is left empty.
    return build_analysis_result(analysis, job_id="")
