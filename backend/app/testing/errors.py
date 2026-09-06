"""AppError subclasses for the testing layer. Same shape as
app/implementation/errors.py -- each carries its own status_code so the
existing handler needs no new wiring.
"""

from __future__ import annotations

from fastapi import status

from app.core.errors import AppError


class TestGenerationTaskNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "TEST_GENERATION_TASK_NOT_FOUND",
            message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class TestGenerationImplementationMissingError(AppError):
    """Phase 11 generates tests against an already-applied Implementation
    (Phase 10) -- there's nothing to write tests for otherwise."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "TEST_GENERATION_IMPLEMENTATION_MISSING",
            message,
            status_code=status.HTTP_409_CONFLICT,
        )


class TestGenerationNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "TEST_GENERATION_NOT_FOUND",
            message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class TestGenerationFailedError(AppError):
    """The provider returned output that failed schema validation even after
    the one repair round, or every proposed case was a duplicate, or no AI
    provider is configured -- no silent best-effort."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "TEST_GENERATION_FAILED",
            message,
            status_code=status.HTTP_502_BAD_GATEWAY,
        )
