"""Repository pattern for RepositoryFile data access. Mirrors JobRepository's shape."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.repository_file import RepositoryFile


class FileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_create(self, snapshot_id: str, files: list) -> list[RepositoryFile]:
        rows = [
            RepositoryFile(
                snapshot_id=snapshot_id,
                path=f.path,
                size_bytes=f.size_bytes,
                sha256=f.sha256,
                language=f.language,
                is_test=f.is_test,
                is_vendored=f.is_vendored,
                parse_status=f.parse_status,
                parse_error=f.parse_error,
            )
            for f in files
        ]
        self._session.add_all(rows)
        self._session.commit()
        return rows

    def replace_for_snapshot(
        self, snapshot_id: str, files: list
    ) -> list[RepositoryFile]:
        """Used by force=True re-ingestion: wholesale replace a snapshot's file rows."""
        self._session.execute(
            delete(RepositoryFile).where(RepositoryFile.snapshot_id == snapshot_id)
        )
        self._session.commit()
        return self.bulk_create(snapshot_id, files)

    def list_for_snapshot(
        self, snapshot_id: str, *, limit: int = 10_000
    ) -> list[RepositoryFile]:
        stmt = (
            select(RepositoryFile)
            .where(RepositoryFile.snapshot_id == snapshot_id)
            .order_by(RepositoryFile.path)
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())

    def update_parse_status(self, updates: list[tuple[str, str, str | None]]) -> None:
        """Bulk per-row update of (file_id, parse_status, parse_error) -- used by the
        Phase 4 analysis pass, the first thing to ever set parse_status=SYNTAX_ERROR."""
        for file_id, parse_status, parse_error in updates:
            row = self._session.get(RepositoryFile, file_id)
            if row is not None:
                row.parse_status = parse_status
                row.parse_error = parse_error
        if updates:
            self._session.commit()
