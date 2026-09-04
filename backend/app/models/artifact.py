"""Artifact -- a pointer to a stored blob. See docs/DATA_MODEL.md Section 2.1 / Section 4.9.

Phase 3 only ever creates ``kind=WORKSPACE`` rows (the materialized, read-only ingestion
workspace). No ``ArtifactStore``/``FSStore`` abstraction and no GC job land yet (ADR-0009 is
later phase scope) -- ``store`` is always ``"FS"`` and ``uri`` is a plain filesystem path.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base


class ArtifactKind(str, enum.Enum):
    PATCH = "PATCH"
    DIFF = "DIFF"
    LOG = "LOG"
    GRAPH = "GRAPH"
    REPORT = "REPORT"
    TRACE = "TRACE"
    WORKSPACE = "WORKSPACE"
    STDIO = "STDIO"
    PR_BODY = "PR_BODY"
    BENCHMARK = "BENCHMARK"


class ArtifactStoreKind(str, enum.Enum):
    FS = "FS"
    OBJECT = "OBJECT"


class ArtifactRetention(str, enum.Enum):
    EPHEMERAL = "EPHEMERAL"
    RETAINED = "RETAINED"
    PERMANENT = "PERMANENT"


class Artifact(Base):
    __tablename__ = "artifact"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # No FK yet -- Task doesn't exist until a later phase (same pattern as Job.task_id).
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    snapshot_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("repository_snapshot.id", ondelete="CASCADE"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    store: Mapped[str] = mapped_column(String(8), nullable=False)
    uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retention: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ArtifactRetention.EPHEMERAL.value
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_artifact_task_kind", "task_id", "kind"),
        Index("ix_artifact_retention", "retention"),
        Index("ix_artifact_expires_at", "expires_at"),
    )
