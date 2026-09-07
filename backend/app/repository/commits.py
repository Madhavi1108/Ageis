"""Repository pattern for Commit data access.

Idempotent on ``(repository_id, sha)`` -- re-running history extraction updates
the existing rows rather than duplicating them.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commit import Commit


class CommitRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_sha(self, repository_id: str, sha: str) -> Commit | None:
        stmt = select(Commit).where(
            Commit.repository_id == repository_id, Commit.sha == sha
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def list_for_repository(
        self, repository_id: str, *, limit: int = 1000
    ) -> list[Commit]:
        stmt = (
            select(Commit)
            .where(Commit.repository_id == repository_id)
            .order_by(Commit.authored_at.desc().nullslast())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())

    def bulk_upsert(self, repository_id: str, rows: list[dict]) -> list[Commit]:
        """``rows`` = ``[{sha, authored_at, author_email_hash, message,
        files_changed, insertions, deletions, is_related_fix}]``."""
        existing = {
            c.sha: c
            for c in self._session.execute(
                select(Commit).where(Commit.repository_id == repository_id)
            )
            .scalars()
            .all()
        }
        out: list[Commit] = []
        for r in rows:
            row = existing.get(r["sha"])
            if row is None:
                row = Commit(repository_id=repository_id, sha=r["sha"])
                self._session.add(row)
            row.authored_at = r["authored_at"]
            row.author_email_hash = r["author_email_hash"]
            row.message = r["message"]
            row.files_changed = r["files_changed"]
            row.insertions = r["insertions"]
            row.deletions = r["deletions"]
            row.is_related_fix = r["is_related_fix"]
            out.append(row)
        self._session.commit()
        for row in out:
            self._session.refresh(row)
        return out
