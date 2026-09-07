"""Repository pattern for PullRequest data access. A plain per-task log --
newest by ``created_at``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pull_request import PullRequest


class PullRequestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        task_id: str,
        mode: str,
        title: str,
        body_artifact_id: str,
        state: str,
        branch: str | None = None,
        commit_sha: str | None = None,
        github_url: str | None = None,
        github_number: int | None = None,
        failure_reason: str | None = None,
    ) -> PullRequest:
        row = PullRequest(
            task_id=task_id,
            mode=mode,
            title=title,
            body_artifact_id=body_artifact_id,
            state=state,
            branch=branch,
            commit_sha=commit_sha,
            github_url=github_url,
            github_number=github_number,
            failure_reason=failure_reason,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return row

    def get_latest_by_task(self, task_id: str) -> PullRequest | None:
        stmt = (
            select(PullRequest)
            .where(PullRequest.task_id == task_id)
            .order_by(PullRequest.created_at.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def list_for_task(self, task_id: str) -> list[PullRequest]:
        stmt = (
            select(PullRequest)
            .where(PullRequest.task_id == task_id)
            .order_by(PullRequest.created_at.asc())
        )
        return list(self._session.execute(stmt).scalars().all())
