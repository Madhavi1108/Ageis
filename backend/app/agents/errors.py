"""AppError subclasses for the agent layer. Same shape as
app/analysis/errors.py -- each carries its own status_code so the existing
handler needs no new wiring.
"""

from __future__ import annotations

from fastapi import status

from app.core.errors import AppError


class PlanTaskNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "PLAN_TASK_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )


class PlanInputsMissingError(AppError):
    """Planning consumes the Phase 7 mapping + the Phase 8 impact analysis; both
    must exist first."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "PLAN_INPUTS_MISSING", message, status_code=status.HTTP_409_CONFLICT
        )


class PlanNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "PLAN_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )


class PlanGenerationFailedError(AppError):
    """The provider returned output that failed schema validation even after the
    one repair round -- no silent best-effort (docs/AI_AGENT_DESIGN.md Section 3)."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "PLAN_GENERATION_FAILED",
            message,
            status_code=status.HTTP_502_BAD_GATEWAY,
        )
