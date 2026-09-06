"""Standalone execution-lookup API. See docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 20. Task-scoped listing lives on the /tasks router
(GET /tasks/{id}/executions); this is the by-id lookup the plan lists
separately (GET /executions/{id}), mirroring app/api/mapping.py's precedent
of a top-level router for something that's conceptually part of a task.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.execution import TestExecution
from app.services import execution as execution_service

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("/{execution_id}", response_model=TestExecution)
def get_execution(execution_id: str, db: Session = Depends(get_db)) -> TestExecution:
    return execution_service.get_execution(db, execution_id)
