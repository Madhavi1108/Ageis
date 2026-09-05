"""Repository pattern for RepositoryAnalysis data access.

Unlike Symbol/Dependency/File, RepositoryAnalysis is a single row per snapshot that gets
rewritten in place on re-analysis -- upsert (update-if-exists, else create), not
delete-then-recreate.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.repository_analysis import RepositoryAnalysis


class AnalysisRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_snapshot(self, snapshot_id: str) -> RepositoryAnalysis | None:
        stmt = select(RepositoryAnalysis).where(
            RepositoryAnalysis.snapshot_id == snapshot_id
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        snapshot_id: str,
        *,
        entry_points: list,
        test_framework: str | None,
        test_command: str | None,
        package_manager: str | None,
        build_backend: str | None,
        summary: dict,
        unknowns: list,
        analysed_at: datetime,
        duration_ms: int,
    ) -> RepositoryAnalysis:
        existing = self.get_by_snapshot(snapshot_id)
        if existing is None:
            row = RepositoryAnalysis(
                snapshot_id=snapshot_id,
                entry_points=entry_points,
                test_framework=test_framework,
                test_command=test_command,
                package_manager=package_manager,
                build_backend=build_backend,
                summary=summary,
                unknowns=unknowns,
                analysed_at=analysed_at,
                duration_ms=duration_ms,
            )
            self._session.add(row)
        else:
            row = existing
            row.entry_points = entry_points
            row.test_framework = test_framework
            row.test_command = test_command
            row.package_manager = package_manager
            row.build_backend = build_backend
            row.summary = summary
            row.unknowns = unknowns
            row.analysed_at = analysed_at
            row.duration_ms = duration_ms
        self._session.commit()
        self._session.refresh(row)
        return row

    def set_graph_artifact_id(
        self, snapshot_id: str, artifact_id: str
    ) -> RepositoryAnalysis | None:
        """Additive, Phase 5 only: point the analysis row at the GRAPH-kind
        Artifact just written. Deliberately separate from upsert() so Phase
        4's call site and contract are untouched."""
        row = self.get_by_snapshot(snapshot_id)
        if row is None:
            return None
        row.graph_artifact_id = artifact_id
        self._session.commit()
        self._session.refresh(row)
        return row
