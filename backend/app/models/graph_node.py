"""GraphNode -- one node in a snapshot's code graph. See
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13 and docs/DATA_MODEL.md Section 2.1.

Node kinds actually produced by Phase 5: FILE, MODULE, CLASS, FUNCTION, TEST,
DEPENDENCY. REPO, COMMIT, ISSUE, PATCH are Specification-defined kinds this
table can also hold once later phases (Git integration, task/patch tracking)
start writing them -- same pattern as RepositoryAnalysis.graph_artifact_id
sitting unused until this phase.
"""
from __future__ import annotations

import enum

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base


class NodeType(str, enum.Enum):
    REPO = "REPO"
    FILE = "FILE"
    MODULE = "MODULE"
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    TEST = "TEST"
    DEPENDENCY = "DEPENDENCY"
    COMMIT = "COMMIT"
    ISSUE = "ISSUE"
    PATCH = "PATCH"


class GraphNode(Base):
    __tablename__ = "graph_node"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_snapshot.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # File path, a "{path}::{qualname}" symbol_id, "dep::{target}", or
    # "unresolved::{expr}" -- always unique per snapshot (builder.py never
    # emits the same ref twice within one build).
    ref: Mapped[str] = mapped_column(String(1536), nullable=False)
    label: Mapped[str] = mapped_column(String(1536), nullable=False)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("snapshot_id", "ref", name="uq_graph_node_snapshot_ref"),
        Index("ix_graph_node_snapshot_type", "snapshot_id", "node_type"),
        Index("ix_graph_node_snapshot_ref", "snapshot_id", "ref"),
    )
