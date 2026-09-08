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


class UnsafeGeneratedCodeError(AppError):
    """A generated test file was blocked by the pre-execution static safety
    scan (docs/SECURITY_MODEL.md Section 2/3): a forbidden call/import
    (``eval``/``exec``/``subprocess``/``socket``/...), a hard-coded secret
    literal, a workspace-escaping path, or a syntax error. AEGIS never writes
    or runs such a file -- the job fails with the finding list."""

    def __init__(self, message: str, *, findings: list[dict] | None = None) -> None:
        super().__init__(
            "GENERATED_CODE_UNSAFE",
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"findings": findings or []},
        )


class RegressionTaskNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "REGRESSION_TASK_NOT_FOUND",
            message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class RegressionInputsMissingError(AppError):
    """Regression selection classifies tests against the Phase 8 impact
    analysis -- it must exist first (GET /tasks/{id}/impact)."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "REGRESSION_INPUTS_MISSING",
            message,
            status_code=status.HTTP_409_CONFLICT,
        )
