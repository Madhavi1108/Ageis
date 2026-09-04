"""Repository pattern for Artifact data access. Mirrors JobRepository's shape."""

from __future__ import annotations

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
        )
        self._session.add(artifact)
        self._session.commit()
        self._session.refresh(artifact)
        return artifact

    def get(self, artifact_id: str) -> Artifact | None:
        return self._session.get(Artifact, artifact_id)
