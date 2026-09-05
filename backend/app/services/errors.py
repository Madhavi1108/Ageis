"""AppError subclasses specific to task / issue ingestion.

Every subtype carries its own status_code, so the existing app_error_handler
(app/core/errors.py, registered in app/main.py's create_app()) renders them all
without any new exception-handler wiring -- same pattern as app/ingestion/errors.py.
"""

from __future__ import annotations

from typing import Any

from fastapi import status

from app.core.errors import AppError


class TaskNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "TASK_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )


class TaskRepositoryNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "TASK_REPO_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )


class InvalidTaskInputError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "TASK_INVALID_INPUT",
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class EmptyTaskTextError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "TASK_EMPTY_TEXT",
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class DuplicateTaskError(AppError):
    def __init__(self, message: str, *, existing_task_id: str) -> None:
        super().__init__(
            "TASK_DUPLICATE",
            message,
            status_code=status.HTTP_409_CONFLICT,
            details={"existing_task_id": existing_task_id},
        )


class TaskStateError(AppError):
    def __init__(
        self, message: str, *, current_state: str, attempted: str
    ) -> None:
        details: dict[str, Any] = {
            "current_state": current_state,
            "attempted": attempted,
        }
        super().__init__(
            "TASK_INVALID_STATE",
            message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )
