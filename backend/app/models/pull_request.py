"""PullRequest -- a generated PR artifact and/or a real GitHub PR
(docs/DATA_MODEL.md Section 2.4, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 27,
ADR-0015).

A plain 1-to-many per task (newest by ``created_at``) -- no supersede chain,
no unique constraint. ``state`` is ``DRAFTED`` (a local PR-body artifact was
produced, or a GitHub PR is pending human approval), ``CREATED`` (a real
GitHub ``201`` came back with a URL/number -- the *only* way this value is
ever written), or ``FAILED`` (a GitHub call returned a structured error).
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base, TimestampMixin


class PullRequest(Base, TimestampMixin):
    __tablename__ = "pull_request"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False)  # LOCAL_ARTIFACT | GITHUB
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body_artifact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("artifact.id", ondelete="RESTRICT"), nullable=False
    )
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    github_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)  # DRAFTED | CREATED | FAILED
    failure_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)

    __table_args__ = (
        Index("ix_pull_request_task_id", "task_id"),
        Index("ix_pull_request_state", "state"),
    )
