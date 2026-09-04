"""AppError subclasses specific to repository ingestion.

Every subtype carries its own status_code, so the existing app_error_handler
(app/core/errors.py, registered in app/main.py's create_app()) handles them all
without any new exception-handler wiring.
"""

from __future__ import annotations

from fastapi import status

from app.core.errors import AppError


class InvalidRepositoryUrlError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "INGEST_INVALID_URL", message, status_code=status.HTTP_400_BAD_REQUEST
        )


class SsrfBlockedError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "INGEST_SSRF_BLOCKED", message, status_code=status.HTTP_400_BAD_REQUEST
        )


class LocalPathNotAllowedError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "INGEST_PATH_NOT_ALLOWED", message, status_code=status.HTTP_400_BAD_REQUEST
        )


class RepositoryNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "INGEST_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )


class RepositoryPrivateOrInaccessibleError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "INGEST_INACCESSIBLE", message, status_code=status.HTTP_403_FORBIDDEN
        )


class CloneTimeoutError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "INGEST_TIMEOUT", message, status_code=status.HTTP_504_GATEWAY_TIMEOUT
        )


class CloneNetworkError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "INGEST_NETWORK_ERROR", message, status_code=status.HTTP_502_BAD_GATEWAY
        )


class RateLimitedError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "INGEST_RATE_LIMITED",
            message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
