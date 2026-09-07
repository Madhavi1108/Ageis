"""AppError subclasses for the engineering-memory layer."""

from __future__ import annotations

from fastapi import status

from app.core.errors import AppError


class MemoryTaskNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "MEMORY_TASK_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )


class MemoryNotFoundError(AppError):
    """No engineering-memory record for this task -- it has not reached a
    terminal state, or ``memory_enabled`` was off when it did."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "MEMORY_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )
