"""Reporting service -- thin orchestration for the /reports API
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 31). Delegates to app/reporting/*;
mirrors app/services/memory.py's top-level-module style.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.reporting.metrics_workbook import build_metrics_workbook
from app.reporting.report_builder import build_task_report, render_task_report_workbook
from app.reporting.excel_import import run_import
from app.schemas.report import ImportResult, TaskReport


def import_workbook(db: Session, *, settings: Settings, data: bytes) -> ImportResult:
    return run_import(db, settings=settings, data=data)


def get_task_report(db: Session, *, settings: Settings, task_id: str) -> TaskReport:
    return build_task_report(db, settings=settings, task_id=task_id)


def get_task_report_xlsx(db: Session, *, settings: Settings, task_id: str) -> bytes:
    report = build_task_report(db, settings=settings, task_id=task_id)
    return render_task_report_workbook(report)


def get_metrics_xlsx(db: Session, *, settings: Settings) -> bytes:
    return build_metrics_workbook(db, settings=settings)
