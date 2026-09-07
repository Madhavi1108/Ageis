"""Per-file churn from a list of ``CommitFact`` (ADR-0014). Pure function --
no Git access, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.git.history import CommitFact


@dataclass
class ChurnStat:
    path: str
    commit_count: int = 0
    insertions: int = 0
    deletions: int = 0
    last_authored_at: datetime | None = None
    _authors: set[str] = field(default_factory=set)

    @property
    def distinct_authors(self) -> int:
        return len(self._authors)


def compute_churn(commits: list[CommitFact]) -> dict[str, ChurnStat]:
    """``{path: ChurnStat}`` aggregated over ``commits``.

    Per-file insertion/deletion splits are not available from
    ``commit.stats.total`` cheaply, so a commit's total add/del count is
    attributed to each file it touched -- a documented approximation that is
    still monotonic in "how much this file moves".
    """
    out: dict[str, ChurnStat] = {}
    for c in commits:
        for path in c.files_changed:
            stat = out.get(path)
            if stat is None:
                stat = ChurnStat(path=path)
                out[path] = stat
            stat.commit_count += 1
            stat.insertions += c.insertions
            stat.deletions += c.deletions
            stat._authors.add(c.author_email)
            if c.authored_at is not None and (
                stat.last_authored_at is None
                or c.authored_at > stat.last_authored_at
            ):
                stat.last_authored_at = c.authored_at
    return out
