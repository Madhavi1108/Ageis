"""Repository pattern for Artifact data access. Mirrors JobRepository's shape."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.artifact import Artifact


class ArtifactRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        kind: str,
        store: str,
        uri: str,
        retention: str,
        snapshot_id: str | None = None,
        task_id: str | None = None,
        sha256: str | None = None,
        size_bytes: int | None = None,
        content_type: str | None = None,
        expires_at: datetime | None = None,
    ) -> Artifact:
        artifact = Artifact(
            kind=kind,
            store=store,
            uri=uri,
            retention=retention,
            snapshot_id=snapshot_id,
            task_id=task_id,
            sha256=sha256,
            size_bytes=size_bytes,
            content_type=content_type,
            expires_at=expires_at,
        )
        self._session.add(artifact)
        self._session.commit()
        self._session.refresh(artifact)
        return artifact

    def get(self, artifact_id: str) -> Artifact | None:
        return self._session.get(Artifact, artifact_id)

    # ---- Phase 27 GC helpers ------------------------------------------ #

    def list_by_retention(self, retention: str) -> list[Artifact]:
        stmt = select(Artifact).where(Artifact.retention == retention)
        return list(self._session.execute(stmt).scalars().all())

    def list_expired(self, now: datetime) -> list[Artifact]:
        """RETAINED/EPHEMERAL artifacts with an ``expires_at`` in the past.
        PERMANENT artifacts have ``expires_at IS NULL`` and never match."""
        stmt = select(Artifact).where(
            Artifact.expires_at.is_not(None), Artifact.expires_at <= now
        )
        return list(self._session.execute(stmt).scalars().all())

    def list_for_task(self, task_id: str) -> list[Artifact]:
        stmt = select(Artifact).where(Artifact.task_id == task_id)
        return list(self._session.execute(stmt).scalars().all())

    def set_expires_at(self, artifact_id: str, when: datetime | None) -> None:
        row = self._session.get(Artifact, artifact_id)
        if row is None:
            return
        row.expires_at = when
        self._session.commit()

    def delete(self, artifact_id: str) -> None:
        row = self._session.get(Artifact, artifact_id)
        if row is None:
            return
        self._session.delete(row)
        self._session.commit()
