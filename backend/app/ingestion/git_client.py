"""GitPython wrapper with ADR-0014 hardening. Never shells out with untrusted strings --
GitPython builds the argv itself; we only ever pass a validated clone_url/path plus fixed flags.
"""

from __future__ import annotations

from pathlib import Path

import git

from app.ingestion.errors import (
    CloneNetworkError,
    CloneTimeoutError,
    RateLimitedError,
    RepositoryNotFoundError,
    RepositoryPrivateOrInaccessibleError,
)

_HARDENING_OPTIONS = ["--no-recurse-submodules", "-c", "core.hooksPath=/dev/null"]


def _map_git_error(exc: git.GitCommandError) -> Exception:
    text = f"{exc.stderr or ''} {exc.status or ''}".lower()
    if (
        "authentication failed" in text
        or "could not read username" in text
        or "permission denied" in text
    ):
        return RepositoryPrivateOrInaccessibleError(
            "clone failed: authentication/permission error"
        )
    if "repository not found" in text or "not found" in text:
        return RepositoryNotFoundError("clone failed: repository not found")
    if "rate limit" in text:
        return RateLimitedError("clone failed: rate limited")
    if exc.status in (None, -9, 143):
        return CloneTimeoutError("clone timed out")
    return CloneNetworkError(f"clone failed: {exc.stderr or exc}")


def clone_shallow(
    clone_url: str, dest: Path, *, depth: int, branch: str | None, timeout_s: int
) -> git.Repo:
    """Shallow-clone `clone_url` into `dest` with hooks/submodules/prompts disabled."""
    try:
        return git.Repo.clone_from(
            clone_url,
            dest,
            depth=depth,
            branch=branch,
            multi_options=_HARDENING_OPTIONS,
            env={"GIT_TERMINAL_PROMPT": "0"},
            kill_after_timeout=timeout_s,
        )
    except git.GitCommandError as exc:
        raise _map_git_error(exc) from exc


def open_local(path: Path) -> git.Repo | None:
    """Open `path` as a git repo if it has a .git directory; None if it's a plain directory
    (that's a valid, non-error LOCAL ingestion target -- see app/ingestion/ingest.py).
    """
    try:
        return git.Repo(path, search_parent_directories=False)
    except git.InvalidGitRepositoryError:
        return None


def head_commit_sha(repo: git.Repo) -> str:
    return repo.head.commit.hexsha


def current_branch(repo: git.Repo) -> str | None:
    try:
        return repo.active_branch.name
    except TypeError:
        return None  # detached HEAD
