"""Engineering-memory API (Phase 20, docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 28). A top-level router, like app/api/executions.py.

``GET /tasks/{id}/memory`` lives on the tasks router (app/api/tasks.py); the
task-agnostic list + search live here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.memory import EngineeringMemoryOut, MemoryHit, MemorySearchRequest
from app.services import memory as memory_service

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("", response_model=list[EngineeringMemoryOut])
def list_memory(
    repository_id: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[EngineeringMemoryOut]:
    """Persisted completed-task records, newest first. Optionally filtered to
    one repository."""
    return memory_service.list_memory(db, repository_id=repository_id, limit=limit)


@router.post("/search", response_model=list[MemoryHit])
def search_memory(
    body: MemorySearchRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[MemoryHit]:
    """Rank prior tasks against a free-text query -- lexical + symbol overlap +
    same-repo boost + recency. Every hit carries a similarity score, provenance,
    and a "historical -- verify" label; results are deterministic and never
    authoritative."""
    return memory_service.search(
        db,
        settings=settings,
        query=body.query,
        repository_id=body.repository_id,
        top_k=body.top_k,
    )
