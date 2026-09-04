"""Repository pattern for RepositorySnapshot data access. Mirrors JobRepository's shape."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.snapshot import RepositorySnapshot, SnapshotStatus


class SnapshotRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        repository_id: str,
        commit_sha: str,
        branch: str | None,
        history_depth: int,
    ) -> RepositorySnapshot:
        snapshot = RepositorySnapshot(
            repository_id=repository_id,
            commit_sha=commit_sha,
            branch=branch,
            history_depth=history_depth,
            status=SnapshotStatus.INGESTING.value,
        )
        self._session.add(snapshot)
        self._session.commit()
        self._session.refresh(snapshot)
        return snapshot

    def get(self, snapshot_id: str) -> RepositorySnapshot | None:
        return self._session.get(RepositorySnapshot, snapshot_id)

    def get_by_commit(
        self, repository_id: str, commit_sha: str
    ) -> RepositorySnapshot | None:
        stmt = select(RepositorySnapshot).where(
            RepositorySnapshot.repository_id == repository_id,
            RepositorySnapshot.commit_sha == commit_sha,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def list_for_repository(
        self, repository_id: str, *, limit: int = 100
    ) -> list[RepositorySnapshot]:
        stmt = (
            select(RepositorySnapshot)
            .where(RepositorySnapshot.repository_id == repository_id)
            .order_by(RepositorySnapshot.id.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())

    def finalize(
        self,
        snapshot_id: str,
        *,
        status: str,
        limit_reason: str | None,
        file_count: int,
        total_bytes: int,
        languages: dict,
        ingested_at: datetime,
    ) -> RepositorySnapshot:
        snapshot = self._session.get(RepositorySnapshot, snapshot_id)
        assert snapshot is not None
        snapshot.status = status
        snapshot.limit_reason = limit_reason
        snapshot.file_count = file_count
        snapshot.total_bytes = total_bytes
        snapshot.languages = languages
        snapshot.ingested_at = ingested_at
        self._session.commit()
        self._session.refresh(snapshot)
        return snapshot
