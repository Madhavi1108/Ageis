"""Engineering-memory service (Phase 20, docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 28, ADR-0016).

* ``record_task``            -- write the ``EngineeringMemory`` row for a task
  that has reached a terminal state, and recompute the per-repository
  ``RepositoryKnowledge`` aggregate. No-op when ``memory_enabled`` is off.
* ``search`` / ``list_memory`` / ``get_for_task`` -- read APIs.
* ``retrieve_hits_for_task`` -- the shared hook mapping / planning / regression
  call to get prior-task evidence for the task in hand (excludes that task).

Memory is evidence, never truth: retrieval never overrides current evidence and
a past patch is never applied.
"""

from __future__ import annotations

from collections import Counter

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.ids import new_id
from app.memory import store
from app.memory import retrieve as retrieve_mod
from app.memory.errors import MemoryNotFoundError, MemoryTaskNotFoundError
from app.models.job import JobType
from app.repository.engineering_memory import EngineeringMemoryRepository
from app.repository.issues import IssueRepository
from app.repository.jobs import JobRepository
from app.repository.repository_knowledge import RepositoryKnowledgeRepository
from app.repository.tasks import TaskRepository
from app.schemas.memory import EngineeringMemoryOut, MemoryHit

_RISKY_FILES_CAP = 50
_RECURRING_CAP = 30
_PRIOR_MAPPINGS_CAP = 100


# --------------------------------------------------------------------------- #
# projection
# --------------------------------------------------------------------------- #


def _project(row) -> EngineeringMemoryOut:
    return EngineeringMemoryOut.model_validate(row, from_attributes=True)


# --------------------------------------------------------------------------- #
# write
# --------------------------------------------------------------------------- #


def record_task(
    db: Session, *, settings: Settings, task_id: str, outcome: str
) -> EngineeringMemoryOut | None:
    """Persist the memory record for ``task_id`` (idempotent). Returns ``None``
    when ``memory_enabled`` is off."""
    if not settings.memory_enabled:
        return None

    task = TaskRepository(db).get(task_id)
    if task is None:
        raise MemoryTaskNotFoundError(f"task {task_id} not found")

    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.MEMORY.value,
        idempotency_key=f"memory:{task_id}:{new_id()}",
        task_id=task_id,
    )
    jobs.mark_running(job.id)
    try:
        record = store.build_record(db, task_id=task_id, outcome=outcome)
        row = EngineeringMemoryRepository(db).upsert(task_id, **record)
        _recompute_knowledge(db, task.repository_id)
    except Exception as exc:  # pragma: no cover - defensive job bookkeeping
        jobs.mark_failed(job.id, error={"code": "MEMORY_FAILED", "message": str(exc)})
        raise
    jobs.mark_succeeded(job.id)
    return _project(row)


def _recompute_knowledge(db: Session, repository_id: str) -> None:
    rows = EngineeringMemoryRepository(db).list(repository_id=repository_id)

    file_count: Counter[str] = Counter()
    file_last: dict[str, str] = {}
    sig_count: Counter[str] = Counter()
    prior: list[dict] = []
    for r in rows:
        seen = r.created_at.isoformat() if r.created_at else ""
        for path in r.touched_files or []:
            file_count[path] += 1
            if path not in file_last or seen > file_last[path]:
                file_last[path] = seen
        for sig in r.failure_signatures or []:
            sig_count[sig] += 1
        prior.append(
            {
                "task_id": r.task_id,
                "issue_summary": " ".join(r.issue_text_sanitized.split())[:160],
                "files": list(r.touched_files or []),
            }
        )

    risky_files = [
        {"path": p, "count": c, "last_seen": file_last.get(p, "")}
        for p, c in file_count.most_common(_RISKY_FILES_CAP)
    ]
    recurring = [
        {"signature": s, "count": c}
        for s, c in sig_count.most_common(_RECURRING_CAP)
        if c >= 2
    ]
    RepositoryKnowledgeRepository(db).upsert(
        repository_id,
        task_count=len(rows),
        risky_files=risky_files,
        recurring_failures=recurring,
        prior_mappings=prior[:_PRIOR_MAPPINGS_CAP],
    )


# --------------------------------------------------------------------------- #
# read
# --------------------------------------------------------------------------- #


def get_for_task(db: Session, task_id: str) -> EngineeringMemoryOut:
    if TaskRepository(db).get(task_id) is None:
        raise MemoryTaskNotFoundError(f"task {task_id} not found")
    row = EngineeringMemoryRepository(db).get_by_task(task_id)
    if row is None:
        raise MemoryNotFoundError(
            f"no engineering-memory record for task {task_id} "
            "(it has not reached a terminal state, or memory was disabled)"
        )
    return _project(row)


def list_memory(
    db: Session, *, repository_id: str | None = None, limit: int = 50
) -> list[EngineeringMemoryOut]:
    return [
        _project(r)
        for r in EngineeringMemoryRepository(db).list(
            repository_id=repository_id, limit=limit
        )
    ]


def search(
    db: Session,
    *,
    settings: Settings,
    query: str,
    repository_id: str | None = None,
    top_k: int | None = None,
    exclude_task_id: str | None = None,
) -> list[MemoryHit]:
    rows = EngineeringMemoryRepository(db).list(repository_id=repository_id)
    return retrieve_mod.retrieve(
        rows,
        query_text=query,
        repository_id=repository_id,
        exclude_task_id=exclude_task_id,
        settings=settings,
        top_k=top_k,
    )


def retrieve_hits_for_task(
    db: Session, *, settings: Settings, task_id: str, top_k: int | None = None
) -> list[MemoryHit]:
    """Prior-task evidence for the task in hand -- ``[]`` when memory is
    disabled, empty, or the task is unknown."""
    if not settings.memory_enabled:
        return []
    task = TaskRepository(db).get(task_id)
    if task is None:
        return []
    if task.issue_id:
        issue = IssueRepository(db).get(task.issue_id)
        query = (
            f"{issue.title}\n{issue.body_sanitized}"
            if issue is not None
            else task.description_sanitized
        )
    else:
        query = task.description_sanitized
    return search(
        db,
        settings=settings,
        query=query,
        repository_id=task.repository_id,
        top_k=top_k,
        exclude_task_id=task_id,
    )


def format_hits(hits: list[MemoryHit]) -> str:
    """A compact, non-authoritative rendering for a prompt's ``memory_hits``
    variable."""
    if not hits:
        return "(none)"
    lines = []
    for h in hits:
        lines.append(
            f"- {h.provenance}: {h.issue_summary} -> {h.fix_summary} "
            f"[{h.label}; similarity {h.similarity:.2f}]"
        )
    return "\n".join(lines)
