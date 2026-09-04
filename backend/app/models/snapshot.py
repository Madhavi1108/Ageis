"""RepositorySnapshot -- an immutable checkout at one commit. See docs/DATA_MODEL.md Section 2.1.

``commit_sha`` is either a real Git commit sha (when the source has a `.git` directory or was
cloned) or a deterministic ``"local:" + sha256(...)``-prefixed pseudo-sha synthesized from the
file manifest when ingesting a plain, non-git local directory (see app/ingestion/ingest.py). The
prefix lets downstream code detect and skip git-history-dependent features gracefully.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base, TimestampMixin


class SnapshotStatus(str, enum.Enum):
    INGESTING = "INGESTING"
    READY = "READY"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    FAILED = "FAILED"


class RepositorySnapshot(Base, TimestampMixin):
    __tablename__ = "repository_snapshot"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    repository_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ingested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    history_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    languages: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=SnapshotStatus.INGESTING.value, index=True
    )
    limit_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)

    __table_args__ = (
        UniqueConstraint("repository_id", "commit_sha", name="uq_snapshot_repo_commit"),
    )
