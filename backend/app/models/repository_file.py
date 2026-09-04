"""RepositoryFile -- one file in a snapshot. See docs/DATA_MODEL.md Section 2.1.

No TimestampMixin: file rows are immutable, created once alongside their snapshot and never
updated in place (a re-ingest with force=True replaces them wholesale, see
app/repository/files.py::FileRepository.replace_for_snapshot).
"""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base


class ParseStatus(str, enum.Enum):
    OK = "OK"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    SKIPPED = "SKIPPED"


class RepositoryFile(Base):
    __tablename__ = "repository_file"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_snapshot.id", ondelete="CASCADE"),
        nullable=False,
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_vendored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parse_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ParseStatus.OK.value
    )
    parse_error: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    __table_args__ = (
        UniqueConstraint("snapshot_id", "path", name="uq_file_snapshot_path"),
        Index("ix_file_snapshot_path", "snapshot_id", "path"),
        Index("ix_file_snapshot_is_test", "snapshot_id", "is_test"),
        Index("ix_file_language", "language"),
    )
