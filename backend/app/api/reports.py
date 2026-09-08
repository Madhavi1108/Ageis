"""Excel import / export + the 18-section task report (Phase 23,
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 31).

A top-level router like app/api/memory.py. Import reuses the same domain
services as POST /repositories and POST /tasks; export is pure reads.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.auth import operator_required
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.report import ImportResult, TaskReport
from app.services import reporting as reporting_service

router = APIRouter(prefix="/reports", tags=["reports"])

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(data: bytes, filename: str) -> Response:
    return Response(
        content=data,
        media_type=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/import",
    status_code=201,
    response_model=ImportResult,
    dependencies=[operator_required],
)
async def import_workbook(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ImportResult:
    """Bulk-create repositories + tasks from an .xlsx workbook sent as the raw
    request body (``--data-binary @workbook.xlsx``). Each row goes through the
    same validation as the API; per-row failures are returned in ``errors`` and
    never abort the rest. Bounded by ``request_max_body_bytes`` (1 MB default)."""
    data = await request.body()
    return reporting_service.import_workbook(db, settings=settings, data=data)


# Declared before ``/tasks/{task_id}`` so the literal ``.xlsx`` suffix wins the
# match (a path param otherwise also matches ``<id>.xlsx``).
@router.get("/tasks/{task_id}.xlsx")
def get_task_report_xlsx(
    task_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    """The 18-section report as a workbook (Overview sheet + one sheet per
    data-bearing section)."""
    data = reporting_service.get_task_report_xlsx(
        db, settings=settings, task_id=task_id
    )
    return _xlsx(data, f"task-{task_id}.xlsx")


@router.get("/tasks/{task_id}", response_model=TaskReport)
def get_task_report(
    task_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TaskReport:
    """The structured 18-section report (Specification Section 33) for a task.
    Sections whose stage has not run are ``present: false`` with a note; the
    builder never triggers a computation."""
    return reporting_service.get_task_report(db, settings=settings, task_id=task_id)


@router.get("/metrics.xlsx")
def get_metrics_xlsx(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    """The corpus metrics workbook: nine sheets pulled from the domain
    repositories across all tasks, plus an Engineering Metrics sheet whose
    derivable metrics are formula cells and whose benchmark-only metrics render
    ``N/A -- <reason>``."""
    data = reporting_service.get_metrics_xlsx(db, settings=settings)
    return _xlsx(data, "aegis-metrics.xlsx")
