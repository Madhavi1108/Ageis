"""AppError subclasses for the Git-intelligence layer. Same shape as
app/scoring/errors.py -- each carries its own status_code.
"""

from __future__ import annotations

from fastapi import status

from app.core.errors import AppError


class GitRepositoryNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "GIT_REPOSITORY_NOT_FOUND",
            message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class GitBlamePathRequiredError(AppError):
    """``GET /repositories/{id}/git/blame`` needs a ``?path=`` query parameter."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "GIT_BLAME_PATH_REQUIRED",
            message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
