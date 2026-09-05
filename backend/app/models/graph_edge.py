"""GraphEdge -- one directed edge in a snapshot's code graph. See
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 13 and docs/DATA_MODEL.md Section 2.1.

Edge kinds actually produced by Phase 5: IMPORTS, DEFINES, TESTS, CALLS.
MODIFIES, DEPENDS_ON, CHANGED_BY, RELATED_TO, FIXED_BY, AFFECTS are
Specification-defined kinds this table can also hold once later phases
populate them (patch tracking, Git integration).

``confidence`` is only meaningful for CALLS edges (RESOLVED / HEURISTIC /
UNRESOLVED -- Specification Section 21: never assert an unresolved call as a
fact); it is null for the other, deterministically-derived edge kinds.
"""
from __future__ import annotations

import enum

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base


class EdgeType(str, enum.Enum):
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    DEFINES = "DEFINES"
    TESTS = "TESTS"
    MODIFIES = "MODIFIES"
    DEPENDS_ON = "DEPENDS_ON"
    CHANGED_BY = "CHANGED_BY"
    RELATED_TO = "RELATED_TO"
    FIXED_BY = "FIXED_BY"
    AFFECTS = "AFFECTS"


class EdgeConfidence(str, enum.Enum):
    RESOLVED = "RESOLVED"
    HEURISTIC = "HEURISTIC"
    UNRESOLVED = "UNRESOLVED"


class GraphEdge(Base):
    __tablename__ = "graph_edge"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_snapshot.id", ondelete="CASCADE"),
        nullable=False,
    )
    edge_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_node_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("graph_node.id", ondelete="CASCADE"), nullable=False
    )
    target_node_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("graph_node.id", ondelete="CASCADE"), nullable=False
    )
    confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_graph_edge_snapshot_type", "snapshot_id", "edge_type"),
        Index("ix_graph_edge_source", "source_node_id"),
        Index("ix_graph_edge_target", "target_node_id"),
    )
