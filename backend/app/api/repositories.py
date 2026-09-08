"""Repository ingestion API. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 11."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.core.auth import operator_required
from app.ingestion.errors import RepositoryNotFoundError
from app.ingestion.ingest import ingest_repository
from app.repository.repositories import RepositoryRepository
from app.services import repositories as repositories_service
from app.git.errors import GitBlamePathRequiredError
from app.schemas.git import BlameHunk, GitContext
from app.schemas.repository import (
    IngestRequest,
    IngestResult,
    RepositoryCreateRequest,
    RepositoryRef,
)
from app.schemas.scoring import RepositoryHealthProfile
from app.services import git_intel as git_intel_service
from app.services import scoring as scoring_service

router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.post(
    "", status_code=201, response_model=RepositoryRef, dependencies=[operator_required]
)
def create_repository(
    body: RepositoryCreateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RepositoryRef:
    return repositories_service.create_repository_ref(db, settings=settings, body=body)


@router.get("/{repository_id}", response_model=RepositoryRef)
def get_repository(repository_id: str, db: Session = Depends(get_db)) -> RepositoryRef:
    repo = RepositoryRepository(db).get(repository_id)
    if repo is None:
        raise RepositoryNotFoundError(f"repository {repository_id} not found")
    return RepositoryRef.model_validate(repo, from_attributes=True)


@router.get("/{repository_id}/health", response_model=RepositoryHealthProfile)
def get_repository_health(
    repository_id: str,
    refresh: bool = False,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RepositoryHealthProfile:
    """The Repository Health Profile for this repository's newest analysed
    snapshot (Phase 17): a deterministic, versioned 0-100 score from weighted
    sub-scores (maintainability, coverage, dependency coupling, churn
    stability, documentation ratio, CI presence) plus ``risky_modules`` (the
    top decile by centrality x churn x inverse-coverage x complexity).
    Sub-scores with no data source in this environment carry the documented
    neutral prior. Computed and persisted on first access (or ``?refresh=true``);
    requires at least one analysed snapshot (409)."""
    return scoring_service.get_or_health(
        db, settings=settings, repository_id=repository_id, refresh=refresh
    )


@router.get("/{repository_id}/git/history", response_model=GitContext)
def get_git_history(
    repository_id: str,
    limit: int = 50,
    refresh: bool = False,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> GitContext:
    """Recent commits + related-fix commits for this repository's newest
    snapshot (Phase 19). Extracted from a real Git repo on first access (the
    LOCAL origin, or a shallow re-clone for GITHUB) and cached in the ``commit``
    table; ``?refresh=true`` re-extracts. A files-only ingest or a synthesized
    snapshot id yields ``available: false`` (HTTP 200)."""
    return git_intel_service.get_or_extract_history(
        db, settings=settings, repository_id=repository_id, limit=limit, refresh=refresh
    )


@router.get("/{repository_id}/git/churn", response_model=GitContext)
def get_git_churn(
    repository_id: str,
    refresh: bool = False,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> GitContext:
    """Per-file churn (commit count, insertions, deletions, distinct authors)
    over the extracted history."""
    return git_intel_service.get_or_extract_history(
        db, settings=settings, repository_id=repository_id, refresh=refresh
    )


@router.get("/{repository_id}/git/blame", response_model=list[BlameHunk])
def get_git_blame(
    repository_id: str,
    path: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[BlameHunk]:
    """``git blame`` hunks for ``?path=`` at HEAD (author emails hashed).
    Returns ``[]`` when no Git history is reachable or the path is untracked."""
    if not path:
        raise GitBlamePathRequiredError("git blame requires a ?path= query parameter")
    return git_intel_service.get_blame(
        db, settings=settings, repository_id=repository_id, path=path
    )


@router.get("/{repository_id}/git/context", response_model=GitContext)
def get_git_context(
    repository_id: str,
    limit: int = 50,
    refresh: bool = False,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> GitContext:
    """The full assembled Git context: commits, churn, and related fixes."""
    return git_intel_service.get_or_extract_history(
        db, settings=settings, repository_id=repository_id, limit=limit, refresh=refresh
    )


@router.post(
    "/{repository_id}/snapshots",
    status_code=201,
    response_model=IngestResult,
    dependencies=[operator_required],
)
def create_snapshot(
    repository_id: str,
    body: IngestRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> IngestResult:
    repo = RepositoryRepository(db).get(repository_id)
    if repo is None:
        raise RepositoryNotFoundError(f"repository {repository_id} not found")
    return ingest_repository(db, repository=repo, request=body, settings=settings)
