"""AppError subclasses for reporting / Excel import-export.

Each subtype fixes its own code + status_code, so the app_error_handler
registered in app/main.py renders them with no new wiring -- same pattern as
app/ingestion/errors.py and app/services/errors.py.
"""

from __future__ import annotations

from typing import Any

from fastapi import status

from app.core.errors import AppError


class ReportTaskNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "REPORT_TASK_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )


class WorkbookSchemaError(AppError):
    """A structural problem with an uploaded workbook (missing sheet/column)."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            "REPORT_WORKBOOK_SCHEMA",
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class WorkbookParseError(AppError):
    """The uploaded bytes are not a readable .xlsx workbook."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "REPORT_WORKBOOK_PARSE",
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
