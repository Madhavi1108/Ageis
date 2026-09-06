"""AppError subclasses for failure investigation. Same shape as
app/sandbox/errors.py -- each carries its own status_code.
"""

from __future__ import annotations

from fastapi import status

from app.core.errors import AppError


class FailureTaskNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "FAILURE_TASK_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )


class NoFailingExecutionError(AppError):
    """There is no failing TestExecution to investigate -- the latest run passed,
    did not run (PARTIALLY_SUPPORTED), or does not exist yet."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "NO_FAILING_EXECUTION", message, status_code=status.HTTP_409_CONFLICT
        )
