"""RepositoryKnowledge -- the per-repository aggregate over its engineering
memory (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 28, ADR-0016 "Repository
knowledge" layer).

DATA_MODEL.md has no RepositoryKnowledge entity; this is a deliberate extension
(the same precedent Phase 15's ``regression_plan`` and Phase 17's
``repository_health`` set). One upserted row per repository, **recomputed** from
every ``EngineeringMemory`` row for that repo each time a task terminal-state
record is written. Static structure / test / build facts live on
``RepositoryAnalysis`` (per snapshot) -- this table only carries the
memory-derived, cross-task facts: which files move often, which failure
signatures recur, and a compact issue -> files history.
"""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id
from app.models.base import Base, TimestampMixin


class RepositoryKnowledge(Base, TimestampMixin):
    __tablename__ = "repository_knowledge"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repository.id", ondelete="CASCADE"), nullable=False
    )
    task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # [{path, count, last_seen}]
    risky_files: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # [{signature, count}]
    recurring_failures: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # [{task_id, issue_summary, files}]
    prior_mappings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    __table_args__ = (
        UniqueConstraint("repository_id", name="uq_repository_knowledge_repository"),
        Index("ix_repository_knowledge_repository_id", "repository_id"),
    )
