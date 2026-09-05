"""ImpactAnalysis -- the persisted ``ImpactAnalysis`` result for a task. See
docs/DATA_MODEL.md Section 2.2 ("ImpactAnalysis") and
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 16.

One row per task (``UniqueConstraint(task_id)``), rewritten in place when
recomputed -- upsert, same shape as RepositoryAnalysis / CodeMapping. Every
structured section is a JSON document (read/written whole, never queried
field-by-field, docs/DATA_MODEL.md Section 4).

The human-readable report is *not* stored: it is rendered from these fields on
read (app/services/impact.py) so it can never drift from the machine bundle.
"""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base, TimestampMixin


class ImpactAnalysis(Base, TimestampMixin):
    __tablename__ = "impact_analysis"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("task.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("repository_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # {files: [path], symbols: [symbol_id]}
    changed_set: Mapped[dict] = mapped_column(JSON, nullable=False)
    # {"1": [ref], "2": [ref], ...} -- reverse-graph BFS by hop distance
    blast_radius: Mapped[dict] = mapped_column(JSON, nullable=False)
    # [{symbol, callers: [{ref, hop, edge_confidence}]}]
    callers: Mapped[list] = mapped_column(JSON, nullable=False)
    related_tests: Mapped[list] = mapped_column(JSON, nullable=False)
    # [{symbol_id, reason}]
    public_api_touched: Mapped[list] = mapped_column(JSON, nullable=False)
    # [{ref, detail}] -- always basis INFERENCE
    config_refs: Mapped[list] = mapped_column(JSON, nullable=False)
    db_refs: Mapped[list] = mapped_column(JSON, nullable=False)
    # [{path, score, reason}]
    regression_areas: Mapped[list] = mapped_column(JSON, nullable=False)
    # {signal: {value, normalized, basis, unavailable_reason}}
    risk_signal_bundle: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("task_id", name="uq_impact_analysis_task"),
        Index("ix_impact_analysis_task_id", "task_id"),
        Index("ix_impact_analysis_snapshot_id", "snapshot_id"),
    )
