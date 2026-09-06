"""AppError subclasses for the implementation layer. Same shape as
app/agents/errors.py -- each carries its own status_code so the existing
handler needs no new wiring.
"""

from __future__ import annotations

from fastapi import status

from app.core.errors import AppError


class ImplementationTaskNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "IMPLEMENTATION_TASK_NOT_FOUND",
            message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ImplementationPlanNotApprovedError(AppError):
    """Phase 10 only ever applies an APPROVED plan -- stricter than Phase 9's
    own "mapping + impact exist" gate, since here real code is written."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "IMPLEMENTATION_PLAN_NOT_APPROVED",
            message,
            status_code=status.HTTP_409_CONFLICT,
        )


class ImplementationNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "IMPLEMENTATION_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )


class ImplementationFailedError(AppError):
    """The provider returned output that failed schema validation even after
    the one repair round, or every edit-op attempt hit an EditorError, or no
    AI provider is configured -- no silent best-effort (a fabricated code
    edit is not a safe fallback, unlike the deterministic planning skeleton)."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "IMPLEMENTATION_FAILED",
            message,
            status_code=status.HTTP_502_BAD_GATEWAY,
        )
