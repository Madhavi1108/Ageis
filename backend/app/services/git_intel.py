"""Git-intelligence service (Phase 19, docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 27).

``get_or_extract_history`` opens a real Git repo for the repository's newest
snapshot (``app/git/repo_access.open_repo``), extracts the newest commits,
hashes author emails with a per-repository salt, classifies related fixes, and
upserts ``Commit`` rows -- then assembles a ``GitContext``. Cached: a second
call reads the ``commit`` table without touching Git unless ``refresh=True``.
When no Git history is reachable (files-only ingest, ``"local:"`` pseudo-sha)
the result is ``GitContext(available=False, reason=...)`` -- HTTP 200, not an
error.
"""

from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.ids import new_id
from app.git.blame import blame_file
from app.git.churn import compute_churn
from app.git.history import CommitFact, extract_commits
from app.git.queries import is_related_fix
from app.git.repo_access import open_repo
from app.models.job import JobType
from app.repository.commits import CommitRepository
from app.repository.impact_analyses import ImpactAnalysisRepository
from app.repository.code_mappings import CodeMappingRepository
from app.repository.jobs import JobRepository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.repository.tasks import TaskRepository
from app.schemas.git import BlameHunk, ChurnEntry, CommitInfo, GitContext
from app.git.errors import GitRepositoryNotFoundError


def _hash_email(repository_id: str, email: str) -> str:
    return hashlib.sha256(f"{repository_id}:{email}".encode("utf-8")).hexdigest()


def _newest_snapshot(db: Session, repository_id: str):
    snaps = SnapshotRepository(db).list_for_repository(repository_id)
    return snaps[0] if snaps else None


def _commit_info(row) -> CommitInfo:
    return CommitInfo(
        sha=row.sha,
        authored_at=row.authored_at,
        author_email_hash=row.author_email_hash,
        message=row.message,
        files_changed=list(row.files_changed or []),
        insertions=row.insertions,
        deletions=row.deletions,
        is_related_fix=row.is_related_fix,
    )


def _facts_from_rows(rows) -> list[CommitFact]:
    return [
        CommitFact(
            sha=r.sha,
            authored_at=r.authored_at,
            author_email=r.author_email_hash,  # already hashed; fine for churn keys
            message=r.message,
            files_changed=list(r.files_changed or []),
            insertions=r.insertions,
            deletions=r.deletions,
        )
        for r in rows
    ]


def _churn_entries(facts: list[CommitFact], *, restrict: set[str] | None = None) -> list[ChurnEntry]:
    stats = compute_churn(facts)
    entries = [
        ChurnEntry(
            path=s.path,
            commit_count=s.commit_count,
            insertions=s.insertions,
            deletions=s.deletions,
            distinct_authors=s.distinct_authors,
            last_authored_at=s.last_authored_at,
        )
        for s in stats.values()
        if restrict is None or s.path in restrict
    ]
    entries.sort(key=lambda e: (-e.commit_count, e.path))
    return entries


def _context_from_rows(
    repository_id: str, rows, *, limit: int, restrict: set[str] | None = None
) -> GitContext:
    facts = _facts_from_rows(rows)
    commits = [_commit_info(r) for r in rows[:limit]]
    related = [_commit_info(r) for r in rows if r.is_related_fix][:limit]
    return GitContext(
        repository_id=repository_id,
        available=True,
        commit_count=len(rows),
        commits=commits,
        churn=_churn_entries(facts, restrict=restrict),
        related_fixes=related,
    )


def get_or_extract_history(
    db: Session,
    *,
    settings: Settings,
    repository_id: str,
    limit: int = 50,
    refresh: bool = False,
) -> GitContext:
    repository = RepositoryRepository(db).get(repository_id)
    if repository is None:
        raise GitRepositoryNotFoundError(f"repository {repository_id} not found")

    commit_repo = CommitRepository(db)
    cached = commit_repo.list_for_repository(repository_id)
    if cached and not refresh:
        return _context_from_rows(repository_id, cached, limit=limit)

    snapshot = _newest_snapshot(db, repository_id)
    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.GIT.value,
        idempotency_key=f"git:{repository_id}:{new_id()}",
        task_id=None,
    )
    jobs.mark_running(job.id)

    handle = None
    try:
        handle = open_repo(repository, snapshot, settings)
        if handle is None:
            jobs.mark_succeeded(job.id)
            return GitContext(
                repository_id=repository_id,
                available=False,
                reason="no Git history is reachable for this repository "
                "(files-only ingest or a synthesized snapshot id)",
            )
        facts = extract_commits(
            handle.repo, max_depth=settings.git_history_max_depth
        )
        rows = [
            {
                "sha": f.sha,
                "authored_at": f.authored_at,
                "author_email_hash": _hash_email(repository_id, f.author_email),
                "message": f.message,
                "files_changed": f.files_changed,
                "insertions": f.insertions,
                "deletions": f.deletions,
                "is_related_fix": is_related_fix(f.message),
            }
            for f in facts
        ]
        commit_repo.bulk_upsert(repository_id, rows)
    except Exception as exc:  # pragma: no cover - defensive job bookkeeping
        jobs.mark_failed(job.id, error={"code": "GIT_FAILED", "message": str(exc)})
        raise
    finally:
        if handle is not None:
            handle.cleanup()

    jobs.mark_succeeded(job.id)
    return _context_from_rows(
        repository_id, commit_repo.list_for_repository(repository_id), limit=limit
    )


def get_blame(
    db: Session,
    *,
    settings: Settings,
    repository_id: str,
    path: str,
) -> list[BlameHunk]:
    repository = RepositoryRepository(db).get(repository_id)
    if repository is None:
        raise GitRepositoryNotFoundError(f"repository {repository_id} not found")
    snapshot = _newest_snapshot(db, repository_id)
    handle = open_repo(repository, snapshot, settings)
    if handle is None:
        return []
    try:
        hunks = blame_file(
            handle.repo,
            path,
            hash_email=lambda e: _hash_email(repository_id, e),
        )
    finally:
        handle.cleanup()
    return [
        BlameHunk(
            commit_sha=h.commit_sha,
            author_email_hash=h.author_email_hash,
            lineno_start=h.lineno_start,
            line_count=h.line_count,
            authored_at=h.authored_at,
        )
        for h in hunks
    ]


def get_git_context_for_task(
    db: Session, *, settings: Settings, task_id: str, limit: int = 50
) -> GitContext:
    """Repository history restricted to the files this task touches / maps to."""
    task = TaskRepository(db).get(task_id)
    if task is None:
        raise GitRepositoryNotFoundError(f"task {task_id} not found")
    ctx = get_or_extract_history(
        db, settings=settings, repository_id=task.repository_id, limit=limit
    )
    if not ctx.available:
        return ctx

    scope: set[str] = set()
    mapping = CodeMappingRepository(db).get_by_task(task_id)
    if mapping is not None:
        scope |= {c["path"] for c in (mapping.candidates or [])}
    impact = ImpactAnalysisRepository(db).get_by_task(task_id)
    if impact is not None:
        scope |= set((impact.changed_set or {}).get("files", []))
    if not scope:
        return ctx

    rows = CommitRepository(db).list_for_repository(task.repository_id)
    facts = _facts_from_rows(rows)
    scoped = [r for r in rows if set(r.files_changed or []) & scope]
    return GitContext(
        repository_id=task.repository_id,
        available=True,
        commit_count=len(scoped),
        commits=[_commit_info(r) for r in scoped[:limit]],
        churn=_churn_entries(facts, restrict=scope),
        related_fixes=[_commit_info(r) for r in scoped if r.is_related_fix][:limit],
    )
