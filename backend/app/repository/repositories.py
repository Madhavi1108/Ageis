"""Repository pattern for Repository (the domain entity) data access.

Mirrors app/repository/jobs.py::JobRepository -- create/get/list only, no business logic.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.repository import Repository


class RepositoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create(
        self,
        *,
        source_type: str,
        url_or_path: str,
        name: str,
        owner: str | None = None,
        default_branch: str | None = None,
    ) -> Repository:
        existing = self.get_by_source(source_type, url_or_path)
        if existing is not None:
            return existing
        repo = Repository(
            source_type=source_type,
            url_or_path=url_or_path,
            name=name,
            owner=owner,
            default_branch=default_branch,
        )
        self._session.add(repo)
        self._session.commit()
        self._session.refresh(repo)
        return repo

    def get(self, repository_id: str) -> Repository | None:
        return self._session.get(Repository, repository_id)

    def get_by_source(self, source_type: str, url_or_path: str) -> Repository | None:
        stmt = select(Repository).where(
            Repository.source_type == source_type, Repository.url_or_path == url_or_path
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def list(self, *, limit: int = 100) -> list[Repository]:
        stmt = select(Repository).order_by(Repository.id.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars().all())
