"""Structured GitHub failure modes (ADR-0015). Every HTTP / transport failure
becomes one of these -- callers never see a raw ``httpx`` exception, and the
API never 500s on a GitHub problem.
"""

from __future__ import annotations

from fastapi import status

from app.core.errors import AppError

# Upstream (GitHub-side) failures surface as 502 Bad Gateway; client-correctable
# ones keep their natural status.
_BAD_GATEWAY = status.HTTP_502_BAD_GATEWAY


class GitHubError(AppError):
    """Base for every GitHub failure -- caught wholesale by the PR service so a
    failed call becomes a ``PullRequest(state=FAILED)`` row, not an exception."""

    def __init__(
        self, code: str, message: str, *, status_code: int, github_status: int | None = None
    ) -> None:
        super().__init__(
            code,
            message,
            status_code=status_code,
            details={"github_status": github_status} if github_status else None,
        )
        self.github_status = github_status


class GitHubNotConfiguredError(GitHubError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "GITHUB_NOT_CONFIGURED", message, status_code=status.HTTP_409_CONFLICT
        )


class GitHubAuthError(GitHubError):
    def __init__(self, message: str, *, github_status: int = 401) -> None:
        super().__init__(
            "GITHUB_AUTH_FAILED", message, status_code=_BAD_GATEWAY, github_status=github_status
        )


class GitHubPermissionError(GitHubError):
    def __init__(self, message: str, *, github_status: int = 403) -> None:
        super().__init__(
            "GITHUB_PERMISSION_DENIED",
            message,
            status_code=_BAD_GATEWAY,
            github_status=github_status,
        )


class GitHubNotFoundError(GitHubError):
    def __init__(self, message: str, *, github_status: int = 404) -> None:
        super().__init__(
            "GITHUB_NOT_FOUND",
            message,
            status_code=status.HTTP_404_NOT_FOUND,
            github_status=github_status,
        )


class GitHubConflictError(GitHubError):
    """A branch already exists / a PR already exists / unprocessable entity."""

    def __init__(self, message: str, *, github_status: int = 409) -> None:
        super().__init__(
            "GITHUB_CONFLICT",
            message,
            status_code=status.HTTP_409_CONFLICT,
            github_status=github_status,
        )


class GitHubRateLimitError(GitHubError):
    def __init__(self, message: str, *, github_status: int = 429) -> None:
        super().__init__(
            "GITHUB_RATE_LIMITED",
            message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            github_status=github_status,
        )


class GitHubUnavailableError(GitHubError):
    def __init__(self, message: str, *, github_status: int = 503) -> None:
        super().__init__(
            "GITHUB_UNAVAILABLE",
            message,
            status_code=_BAD_GATEWAY,
            github_status=github_status,
        )


class GitHubNetworkError(GitHubError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "GITHUB_NETWORK_ERROR", message, status_code=_BAD_GATEWAY
        )


# --- PR service (not GitHub-API errors) ---------------------------------- #


class PRTaskNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "PR_TASK_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )


class PRNotVerifiedError(AppError):
    """A pull request is only ever opened for a task whose live verification
    verdict is ``VERIFIED`` (Spec Section 17 / ADR-0015)."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "PR_NOT_VERIFIED", message, status_code=status.HTTP_409_CONFLICT
        )


class PRNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "PR_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )
