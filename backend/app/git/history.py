"""Commit-history extraction via GitPython (ADR-0014).

Pure: takes a ``git.Repo`` and returns plain ``CommitFact`` dataclasses. Email
hashing, ``is_related_fix`` classification, and persistence all happen in
``app/services/git_intel.py`` -- this module only reads the object database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class CommitFact:
    sha: str
    authored_at: datetime | None
    author_email: str
    message: str
    files_changed: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0


def _authored_dt(commit) -> datetime | None:
    try:
        return datetime.fromtimestamp(commit.authored_date, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def extract_commits(repo, *, max_depth: int, rev: str | None = None) -> list[CommitFact]:
    """The newest ``max_depth`` commits reachable from ``rev`` (default HEAD).

    A shallow clone simply yields fewer commits -- not an error.
    """
    facts: list[CommitFact] = []
    try:
        iterator = repo.iter_commits(rev=rev, max_count=max_depth)
    except Exception:  # noqa: BLE001 -- empty repo / bad rev -> no history
        return facts

    for commit in iterator:
        stats = commit.stats
        files_changed = sorted(stats.files.keys())
        facts.append(
            CommitFact(
                sha=commit.hexsha,
                authored_at=_authored_dt(commit),
                author_email=(commit.author.email or "").strip().lower(),
                message=(commit.message or "").strip(),
                files_changed=files_changed,
                insertions=int(stats.total.get("insertions", 0)),
                deletions=int(stats.total.get("deletions", 0)),
            )
        )
    return facts
