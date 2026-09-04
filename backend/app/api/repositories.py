"""Repository ingestion API. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 11."""

from __future__ import annotations

from pathlib import PurePath

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.ingestion.errors import RepositoryNotFoundError
from app.ingestion.ingest import ingest_repository
from app.ingestion.url_validator import validate_local_path, validate_remote_url
from app.repository.repositories import RepositoryRepository
from app.schemas.repository import (
    IngestRequest,
    IngestResult,
    RepositoryCreateRequest,
    RepositoryRef,
)

router = APIRouter(prefix="/repositories", tags=["repositories"])


def _derive_name(url_or_path: str) -> str:
    # PurePath (not Path) so this works for both a local OS path and a URL string
    # (which always uses forward slashes, regardless of platform) without touching
    # the filesystem.
    cleaned = url_or_path.rstrip("/\\")
    if cleaned.endswith(".git"):
        cleaned = cleaned[: -len(".git")]
    return PurePath(cleaned).name or cleaned


@router.post("", status_code=201, response_model=RepositoryRef)
def create_repository(
    body: RepositoryCreateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RepositoryRef:
    if body.source_type == "GITHUB":
        validate_remote_url(body.url_or_path, settings)
    else:
        validate_local_path(body.url_or_path, settings)

    repo = RepositoryRepository(db).get_or_create(
        source_type=body.source_type,
        url_or_path=body.url_or_path,
        name=body.name or _derive_name(body.url_or_path),
        owner=body.owner,
        default_branch=body.default_branch,
    )
    return RepositoryRef.model_validate(repo, from_attributes=True)


@router.get("/{repository_id}", response_model=RepositoryRef)
def get_repository(repository_id: str, db: Session = Depends(get_db)) -> RepositoryRef:
    repo = RepositoryRepository(db).get(repository_id)
    if repo is None:
        raise RepositoryNotFoundError(f"repository {repository_id} not found")
    return RepositoryRef.model_validate(repo, from_attributes=True)


@router.post("/{repository_id}/snapshots", status_code=201, response_model=IngestResult)
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
