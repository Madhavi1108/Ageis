"""Issue -> code mapping API. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 15.

``POST /analysis/map`` computes a mapping. With ``task_id`` it binds a snapshot
and persists the result (readable afterwards at ``GET /tasks/{id}/mapping``);
with ``snapshot_id`` + ``issue_text`` it is stateless. All heavy lifting is in
app/services/mapping.py; this handler is thin.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.mapping import IssueCodeMapping, MapRequest
from app.services import mapping as mapping_service

router = APIRouter(prefix="/analysis", tags=["mapping"])


@router.post("/map", status_code=201, response_model=IssueCodeMapping)
def create_mapping(
    body: MapRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> IssueCodeMapping:
    return mapping_service.run_mapping(
        db,
        settings=settings,
        task_id=body.task_id,
        snapshot_id=body.snapshot_id,
        issue_text=body.issue_text,
        top_k=body.top_k,
    )
