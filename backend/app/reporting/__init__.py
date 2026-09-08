"""Excel import/export + the 18-section task report (Phase 23,
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 31).

Domain-services-only per AEGIS_ARCHITECTURE.md Section 3: this package reads
through the repository layer and the existing stage services and never issues
bespoke SQL or mutates state.
"""

from __future__ import annotations

from app.reporting.excel_import import parse_import_workbook, run_import
from app.reporting.metrics_workbook import build_metrics_workbook
from app.reporting.report_builder import (
    build_task_report,
    render_task_report_workbook,
)

__all__ = [
    "parse_import_workbook",
    "run_import",
    "build_metrics_workbook",
    "build_task_report",
    "render_task_report_workbook",
]
