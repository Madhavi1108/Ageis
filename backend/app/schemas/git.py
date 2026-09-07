"""Local Git-intelligence schemas (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 27,
ADR-0014). Plain Pydantic v2.

``GitContext`` is the assembled answer for a repository: recent commits,
per-file churn, and the commits Git intelligence flagged as related fixes.
``available`` is ``false`` (with a ``reason``) when no real Git history is
reachable -- a plain files-only ingest, or a ``"local:"`` pseudo-sha snapshot
-- which is a normal state, not an error (HTTP 200).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CommitInfo(BaseModel):
    sha: str
    authored_at: datetime | None = None
    author_email_hash: str
    message: str
    files_changed: list[str] = Field(default_factory=list)
    insertions: int = 0
    deletions: int = 0
    is_related_fix: bool = False


class ChurnEntry(BaseModel):
    path: str
    commit_count: int
    insertions: int
    deletions: int
    distinct_authors: int
    last_authored_at: datetime | None = None


class BlameHunk(BaseModel):
    commit_sha: str
    author_email_hash: str
    lineno_start: int
    line_count: int
    authored_at: datetime | None = None


class GitContext(BaseModel):
    repository_id: str
    available: bool
    reason: str | None = None
    commit_count: int = 0
    commits: list[CommitInfo] = Field(default_factory=list)
    churn: list[ChurnEntry] = Field(default_factory=list)
    related_fixes: list[CommitInfo] = Field(default_factory=list)
