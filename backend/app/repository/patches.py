"""Repository pattern for Patch data access. Mirrors JobRepository's shape.

One non-candidate Patch per Implementation today; ``is_candidate=true`` rows
are reserved for the Phase 14 repair loop (ADR-0008), not written yet.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.implementation import Patch


class PatchRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        implementation_id: str,
        artifact_id: str,
        touched_paths: list,
        diff_size: int,
        is_candidate: bool = False,
    ) -> Patch:
        patch = Patch(
            implementation_id=implementation_id,
            artifact_id=artifact_id,
            touched_paths=touched_paths,
            diff_size=diff_size,
            is_candidate=is_candidate,
        )
        self._session.add(patch)
        self._session.commit()
        self._session.refresh(patch)
        return patch

    def get_by_implementation(self, implementation_id: str) -> Patch | None:
        stmt = select(Patch).where(
            Patch.implementation_id == implementation_id, Patch.is_candidate.is_(False)
        )
        return self._session.execute(stmt).scalar_one_or_none()
