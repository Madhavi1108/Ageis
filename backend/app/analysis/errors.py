"""AppError subclasses specific to repository analysis.

Every subtype carries its own status_code, so the existing app_error_handler
(app/core/errors.py, registered in app/main.py's create_app()) handles them all
without any new exception-handler wiring.
"""

from __future__ import annotations

from fastapi import status

from app.core.errors import AppError


class SnapshotNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "ANALYSIS_SNAPSHOT_NOT_FOUND",
            message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class SnapshotNotReadyError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "ANALYSIS_SNAPSHOT_NOT_READY", message, status_code=status.HTTP_409_CONFLICT
        )


class AnalysisNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "ANALYSIS_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )


class ImpactTaskNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "IMPACT_TASK_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )


class ImpactMappingMissingError(AppError):
    """Impact analysis is derived from the Phase 7 issue -> code mapping; it must
    exist first (POST /analysis/map)."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "IMPACT_MAPPING_MISSING", message, status_code=status.HTTP_409_CONFLICT
        )
