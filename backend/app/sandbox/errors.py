"""AppError subclasses for the sandbox-execution layer. Same shape as
app/implementation/errors.py -- each carries its own status_code so the
existing handler needs no new wiring.
"""

from __future__ import annotations

from fastapi import status

from app.core.errors import AppError


class TestExecutionTaskNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "TEST_EXECUTION_TASK_NOT_FOUND",
            message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class TestExecutionTestsMissingError(AppError):
    """Phase 12 executes the tests Phase 11 generated -- there's nothing to
    run otherwise."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "TEST_EXECUTION_TESTS_MISSING",
            message,
            status_code=status.HTTP_409_CONFLICT,
        )


class TestExecutionNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "TEST_EXECUTION_NOT_FOUND",
            message,
            status_code=status.HTTP_404_NOT_FOUND,
        )
