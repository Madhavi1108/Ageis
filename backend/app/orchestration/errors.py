"""AppError subclasses for the orchestration layer."""

from __future__ import annotations

from fastapi import status

from app.core.errors import AppError


class IllegalStateTransitionError(AppError):
    def __init__(self, frm: str, to: str) -> None:
        super().__init__(
            "ILLEGAL_STATE_TRANSITION",
            f"illegal task-state transition {frm} -> {to}",
            status_code=status.HTTP_409_CONFLICT,
            details={"from": frm, "to": to},
        )


class JobNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "JOB_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )


class JobNotCancellableError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "JOB_NOT_CANCELLABLE", message, status_code=status.HTTP_409_CONFLICT
        )
