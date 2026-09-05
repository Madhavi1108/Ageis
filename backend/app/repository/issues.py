"""Repository pattern for Issue data access. Mirrors JobRepository's shape --
create/get only, no business logic (that's app/services/tasks.py).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.issue import Issue


class IssueRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        repository_id: str,
        source: str,
        title: str,
        body_sanitized: str,
        external_ref: str | None = None,
    ) -> Issue:
        issue = Issue(
            repository_id=repository_id,
            source=source,
            title=title,
            body_sanitized=body_sanitized,
            external_ref=external_ref,
        )
        self._session.add(issue)
        self._session.commit()
        self._session.refresh(issue)
        return issue

    def get(self, issue_id: str) -> Issue | None:
        return self._session.get(Issue, issue_id)

    def get_by_external_ref(
        self, repository_id: str, source: str, external_ref: str
    ) -> Issue | None:
        stmt = select(Issue).where(
            Issue.repository_id == repository_id,
            Issue.source == source,
            Issue.external_ref == external_ref,
        )
        return self._session.execute(stmt).scalar_one_or_none()
