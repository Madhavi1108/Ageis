"""Repository pattern for Dependency data access. Mirrors FileRepository's shape."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.dependency import Dependency


class DependencyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_create(self, snapshot_id: str, deps: list) -> list[Dependency]:
        rows = [
            Dependency(
                snapshot_id=snapshot_id,
                kind=d.kind,
                from_file_id=d.from_file_id,
                target=d.target,
                classification=d.classification,
                version_spec=d.version_spec,
                extras=d.extras,
            )
            for d in deps
        ]
        self._session.add_all(rows)
        self._session.commit()
        return rows

    def replace_for_snapshot(self, snapshot_id: str, deps: list) -> list[Dependency]:
        self._session.execute(
            delete(Dependency).where(Dependency.snapshot_id == snapshot_id)
        )
        self._session.commit()
        return self.bulk_create(snapshot_id, deps)

    def list_for_snapshot(
        self,
        snapshot_id: str,
        *,
        classification: str | None = None,
        limit: int = 10_000,
    ) -> list[Dependency]:
        stmt = select(Dependency).where(Dependency.snapshot_id == snapshot_id)
        if classification is not None:
            stmt = stmt.where(Dependency.classification == classification)
        stmt = stmt.limit(limit)
        return list(self._session.execute(stmt).scalars().all())
