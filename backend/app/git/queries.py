"""The four Git-history questions from Spec Section 15 (ADR-0014), as pure
functions over a ``list[CommitFact]``:

1. has this area changed recently?              -> ``area_changed_recently``
2. what happened after that change?             -> ``commits_after``
3. was a similar bug fixed before?              -> ``similar_fix_before``
4. which tests changed with similar edits?      -> ``tests_changed_with``
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from app.git.history import CommitFact

_FIX_RE = re.compile(
    r"\b(fix(e[sd])?|bug(fix)?|regression|hotfix|patch(ed)?|resolve[sd]?)\b",
    re.IGNORECASE,
)
_TEST_PATH_RE = re.compile(r"(^|/)(tests?|test)[/_]|(^|/)test_[^/]+\.py$|_test\.py$")


def is_related_fix(message: str) -> bool:
    """A commit message that reads like a bug/regression fix."""
    return bool(_FIX_RE.search(message or ""))


def _overlaps(files: list[str], paths: set[str]) -> bool:
    return any(f in paths for f in files)


def area_changed_recently(
    commits: list[CommitFact], paths: set[str], *, within_days: int = 90
) -> list[CommitFact]:
    """Commits within ``within_days`` that touched any of ``paths``."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=within_days)
    return [
        c
        for c in commits
        if _overlaps(c.files_changed, paths)
        and c.authored_at is not None
        and c.authored_at >= cutoff
    ]


def commits_after(commits: list[CommitFact], sha: str) -> list[CommitFact]:
    """Every commit newer than ``sha`` (``commits`` is newest-first, as
    ``extract_commits`` returns it). Empty if ``sha`` is not in the range."""
    out: list[CommitFact] = []
    for c in commits:
        if c.sha.startswith(sha) or sha.startswith(c.sha):
            return out
        out.append(c)
    return []  # sha not found -> we cannot say what came "after"


def similar_fix_before(
    commits: list[CommitFact], paths: set[str]
) -> list[CommitFact]:
    """Prior fix-shaped commits that touched any of ``paths``."""
    return [
        c
        for c in commits
        if is_related_fix(c.message) and _overlaps(c.files_changed, paths)
    ]


def tests_changed_with(commits: list[CommitFact], path: str) -> set[str]:
    """Test files that were committed together with ``path``."""
    tests: set[str] = set()
    for c in commits:
        if path not in c.files_changed:
            continue
        for f in c.files_changed:
            if f != path and _TEST_PATH_RE.search(f):
                tests.add(f)
    return tests
