"""AppError subclasses for the verification layer. Same shape as
app/scoring/errors.py -- each carries its own status_code, so the existing
handler in app/main.py needs no new wiring.
"""

from __future__ import annotations

from fastapi import status

from app.core.errors import AppError


class VerificationTaskNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "VERIFICATION_TASK_NOT_FOUND",
            message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class VerificationImplementationMissingError(AppError):
    """Verification checks the patch produced by Phase 10 -- there is nothing
    to verify otherwise (POST /tasks/{id}/changes)."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "VERIFICATION_IMPLEMENTATION_MISSING",
            message,
            status_code=status.HTTP_409_CONFLICT,
        )


class VerificationPlanMissingError(AppError):
    """Plan alignment and the acceptance checks are derived from the Phase 9
    engineering plan (expected behaviour + steps); it must exist first
    (POST /tasks/{id}/plan)."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "VERIFICATION_PLAN_MISSING",
            message,
            status_code=status.HTTP_409_CONFLICT,
        )


class VerificationNotAwaitingApprovalError(AppError):
    """A decision can only resolve a task that is in AWAITING_APPROVAL with a
    live PARTIAL verification."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "VERIFICATION_NOT_AWAITING_APPROVAL",
            message,
            status_code=status.HTTP_409_CONFLICT,
        )
