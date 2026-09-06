"""AppError subclasses for the code-review layer."""

from __future__ import annotations

from fastapi import status

from app.core.errors import AppError


class ReviewTaskNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "REVIEW_TASK_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )


class ReviewImplementationMissingError(AppError):
    """Phase 16 reviews the patch produced by Phase 10 -- there's nothing to
    review otherwise."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "REVIEW_IMPLEMENTATION_MISSING",
            message,
            status_code=status.HTTP_409_CONFLICT,
        )
