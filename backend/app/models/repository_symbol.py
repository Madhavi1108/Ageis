"""RepositorySymbol -- a module/class/function/method fact. See docs/DATA_MODEL.md Section 2.1.

No TimestampMixin: write-once-per-analysis-run rows, same rationale as RepositoryFile --
a re-analysis with force=True replaces them wholesale (see
app/repository/symbols.py::SymbolRepository.replace_for_snapshot).
"""

from __future__ import annotations

import enum

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base


class SymbolKind(str, enum.Enum):
    MODULE = "MODULE"
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"


class RepositorySymbol(Base):
    __tablename__ = "repository_symbol"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_snapshot.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repository_file.id", ondelete="CASCADE"), nullable=False
    )
    # "{relpath}::{qualname}" -- relpath up to 1024 (matches RepositoryFile.path) plus "::"
    # plus a deeply-nested qualname, so this column is wider than path alone.
    symbol_id: Mapped[str] = mapped_column(String(1536), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    qualname: Mapped[str] = mapped_column(String(1024), nullable=False)
    signature: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    lineno: Mapped[int] = mapped_column(Integer, nullable=False)
    end_lineno: Mapped[int] = mapped_column(Integer, nullable=False)
    decorators: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Text, not String(N): docstrings can be long and shouldn't be silently truncated.
    docstring: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_exported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "symbol_id", name="uq_symbol_snapshot_symbolid"
        ),
        Index("ix_symbol_snapshot_symbolid", "snapshot_id", "symbol_id"),
        Index("ix_symbol_file_id", "file_id"),
        Index("ix_symbol_snapshot_kind", "snapshot_id", "kind"),
    )
