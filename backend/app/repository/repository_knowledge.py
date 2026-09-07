"""Repository pattern for RepositoryKnowledge data access. One upserted row per
repository, recomputed from its EngineeringMemory rows on each memory write.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.repository_knowledge import RepositoryKnowledge


class RepositoryKnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_repository(self, repository_id: str) -> RepositoryKnowledge | None:
        stmt = select(RepositoryKnowledge).where(
            RepositoryKnowledge.repository_id == repository_id
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        repository_id: str,
        *,
        task_count: int,
        risky_files: list,
        recurring_failures: list,
        prior_mappings: list,
    ) -> RepositoryKnowledge:
        row = self.get_by_repository(repository_id)
        if row is None:
            row = RepositoryKnowledge(repository_id=repository_id)
            self._session.add(row)
        row.task_count = task_count
        row.risky_files = risky_files
        row.recurring_failures = recurring_failures
        row.prior_mappings = prior_mappings
        self._session.commit()
        self._session.refresh(row)
        return row
