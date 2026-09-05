"""Issue -- a normalized external issue that may back a Task. See docs/DATA_MODEL.md Section 2.2.

``body_sanitized`` has already been through app/services/tasks.py::normalize_text before a row is
created: control characters stripped, length capped. The raw text is never stored and never
reaches a prompt -- only structured fields do (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 14
security model).
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base


class IssueSource(str, enum.Enum):
    API = "API"
    GITHUB = "GITHUB"
    EXCEL = "EXCEL"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Issue(Base):
    __tablename__ = "issue"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    repository_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    # e.g. a GitHub issue number; null for free-text API submissions.
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body_sanitized: Mapped[str] = mapped_column(Text, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("ix_issue_repository_id", "repository_id"),
        Index("ix_issue_source_external_ref", "source", "external_ref"),
    )
