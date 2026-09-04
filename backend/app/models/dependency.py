"""Dependency -- an import edge or declared package dependency. See docs/DATA_MODEL.md Section 2.1.

No unique constraint: repeat edges are allowed (the same target imported from multiple
files, or the same package declared more than once, are each their own row).
"""

from __future__ import annotations

import enum

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base


class DependencyKind(str, enum.Enum):
    IMPORT = "IMPORT"
    PACKAGE = "PACKAGE"


class DependencyClassification(str, enum.Enum):
    STDLIB = "STDLIB"
    THIRD_PARTY = "THIRD_PARTY"
    LOCAL = "LOCAL"
    UNKNOWN = "UNKNOWN"


class Dependency(Base):
    __tablename__ = "dependency"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_snapshot.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    from_file_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("repository_file.id", ondelete="CASCADE"), nullable=True
    )
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    classification: Mapped[str] = mapped_column(String(16), nullable=False)
    version_spec: Mapped[str | None] = mapped_column(String(128), nullable=True)
    extras: Mapped[list | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_dependency_snapshot_classification", "snapshot_id", "classification"),
        Index("ix_dependency_from_file_id", "from_file_id"),
    )
