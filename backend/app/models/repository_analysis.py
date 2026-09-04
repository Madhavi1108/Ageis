"""RepositoryAnalysis -- the one-row-per-snapshot analysis summary. See docs/DATA_MODEL.md
Section 2.1.

Has TimestampMixin (unlike RepositoryFile/RepositorySymbol/Dependency): this is the one
table that legitimately gets rewritten in place on re-analysis (force=True) rather than
delete-then-recreate, so `updated_at` documents "when was this row last written", distinct
from `analysed_at` which is domain data about the analysis run itself.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base, TimestampMixin


class RepositoryAnalysis(Base, TimestampMixin):
    __tablename__ = "repository_analysis"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_snapshot.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    entry_points: Mapped[list | None] = mapped_column(JSON, nullable=True)
    test_framework: Mapped[str | None] = mapped_column(String(64), nullable=True)
    test_command: Mapped[str | None] = mapped_column(String(512), nullable=True)
    package_manager: Mapped[str | None] = mapped_column(String(32), nullable=True)
    build_backend: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Nullable, unused until Phase 5 produces a GRAPH-kind Artifact.
    graph_artifact_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("artifact.id", ondelete="SET NULL"), nullable=True
    )
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    unknowns: Mapped[list | None] = mapped_column(JSON, nullable=True)
    analysed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
