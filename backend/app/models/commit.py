"""Commit -- a Git commit relevant to history intelligence
(docs/DATA_MODEL.md Section 2.1, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 27,
ADR-0014).

Keyed on the **repository** (not a snapshot): history spans commits, and the
same commit is relevant across every snapshot of a repo. Rows are extracted by
``app/git/history.py`` and upserted by ``CommitRepository`` -- re-running the
extraction is idempotent on ``(repository_id, sha)``.

``author_email_hash`` is ``sha256(f"{repository_id}:{email}")`` -- the raw
author email is never stored (docs/GOVERNANCE.md Section 5: hashed with a
per-repository salt; the repository id is that salt).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base, TimestampMixin


class Commit(Base, TimestampMixin):
    __tablename__ = "commit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repository.id", ondelete="CASCADE"), nullable=False
    )
    sha: Mapped[str] = mapped_column(String(64), nullable=False)
    authored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    author_email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    files_changed: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    insertions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deletions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_related_fix: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    __table_args__ = (
        UniqueConstraint("repository_id", "sha", name="uq_commit_repo_sha"),
        Index("ix_commit_repository_id", "repository_id"),
        Index("ix_commit_authored_at", "authored_at"),
    )
