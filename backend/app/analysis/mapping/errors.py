"""AppError subclasses specific to issue -> code mapping. Mirrors
app/analysis/errors.py's shape exactly -- each carries its own status_code, so
the existing app_error_handler needs no new wiring.
"""

from __future__ import annotations

from fastapi import status

from app.core.errors import AppError


class MappingSnapshotNotReadyError(AppError):
    """No analysable snapshot for the task's repository (none ingested, or
    ingested but not yet analysed / graphed)."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "MAPPING_SNAPSHOT_NOT_READY",
            message,
            status_code=status.HTTP_409_CONFLICT,
        )


class MappingNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "MAPPING_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )


class MappingTaskNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "MAPPING_TASK_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )
