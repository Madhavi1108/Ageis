"""``git blame`` via GitPython (ADR-0014). Pure read; the caller hashes the
author email (``hash_email``) so the raw address never leaves this function.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable


@dataclass
class BlameHunkFact:
    commit_sha: str
    author_email_hash: str
    lineno_start: int
    line_count: int
    authored_at: datetime | None


def _authored_dt(commit) -> datetime | None:
    try:
        return datetime.fromtimestamp(commit.authored_date, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def blame_file(
    repo,
    path: str,
    *,
    hash_email: Callable[[str], str],
    rev: str = "HEAD",
) -> list[BlameHunkFact]:
    """Contiguous blame hunks for ``path`` at ``rev``. Returns ``[]`` when the
    path is untracked / binary / missing rather than raising."""
    try:
        entries = repo.blame(rev, path)
    except Exception:  # noqa: BLE001 -- unknown path / binary / detached HEAD
        return []

    hunks: list[BlameHunkFact] = []
    lineno = 1
    for commit, lines in entries or []:
        count = len(lines)
        hunks.append(
            BlameHunkFact(
                commit_sha=commit.hexsha,
                author_email_hash=hash_email((commit.author.email or "").strip().lower()),
                lineno_start=lineno,
                line_count=count,
                authored_at=_authored_dt(commit),
            )
        )
        lineno += count
    return hunks
