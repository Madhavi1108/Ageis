"""Repository-create orchestration shared by the API and the Excel importer.

The FastAPI handler (app/api/repositories.py) and the reporting importer
(app/reporting/excel_import.py) both call ``create_repository`` so the URL/path
validation and the (source_type, url_or_path) dedupe stay identical -- the same
principle as app/services/tasks.py::create_task backing both callers.
"""

from __future__ import annotations

from pathlib import PurePath

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.ingestion.url_validator import validate_local_path, validate_remote_url
from app.models.repository import Repository
from app.repository.repositories import RepositoryRepository
from app.schemas.repository import RepositoryCreateRequest, RepositoryRef


def derive_name(url_or_path: str) -> str:
    """The fallback repository name when the caller doesn't supply one.

    PurePath (not Path) so it works for both a local OS path and a URL string
    (always forward slashes) without touching the filesystem.
    """
    cleaned = url_or_path.rstrip("/\\")
    if cleaned.endswith(".git"):
        cleaned = cleaned[: -len(".git")]
    return PurePath(cleaned).name or cleaned


def create_repository(
    db: Session, *, settings: Settings, body: RepositoryCreateRequest
) -> Repository:
    if body.source_type == "GITHUB":
        validate_remote_url(body.url_or_path, settings)
    else:
        validate_local_path(body.url_or_path, settings)

    return RepositoryRepository(db).get_or_create(
        source_type=body.source_type,
        url_or_path=body.url_or_path,
        name=body.name or derive_name(body.url_or_path),
        owner=body.owner,
        default_branch=body.default_branch,
    )


def create_repository_ref(
    db: Session, *, settings: Settings, body: RepositoryCreateRequest
) -> RepositoryRef:
    repo = create_repository(db, settings=settings, body=body)
    return RepositoryRef.model_validate(repo, from_attributes=True)
