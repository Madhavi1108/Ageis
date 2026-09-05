"""Task / issue ingestion service. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 14.

Responsibilities:

* **Normalize** untrusted issue text -- CRLF -> LF, strip control / format
  characters (keeping ``\\n`` and ``\\t``), trim per-line and edge whitespace,
  cap length with provenance. Markdown is left intact: it is stored as data, not
  rendered, and never concatenated into a prompt. Downstream phases read the
  structured ``description`` field only.
* **Infer** ``task_type`` by deterministic keyword rules (AI enrichment is
  Phase 7's ``IssueAnalysis``).
* **Deduplicate** via an idempotency key ``sha256(repo_id + "\\0" + normalized_text)``.
* Persist ``Task`` (+ optional ``Issue``) and open the first ``TaskStep``.
* Drive the only transitions this phase owns: ``PENDING -> QUEUED`` on ``run``
  (creating a ``RUN_TASK`` ``Job``) and ``-> CANCELLED`` on ``cancel``.
  Cancellation is cooperative: there is no running worker in Phase 6, so the
  ``CANCELLED`` task row *is* the flag the Phase 21 orchestrator will check
  between stages.
* Assemble the timeline from ``TaskStep`` rows merged with ``Job`` events.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.job import JobState, JobType
from app.models.task import TERMINAL_TASK_STATES, TaskState, TaskType
from app.repository.issues import IssueRepository
from app.repository.jobs import JobRepository
from app.repository.repositories import RepositoryRepository
from app.repository.task_steps import TaskStepRepository
from app.repository.tasks import TaskRepository
from app.schemas.task import (
    NormalizationInfo,
    Task as TaskSchema,
    TaskCreate,
    TaskCreateResponse,
    TaskList,
    TaskTimeline,
    TimelineEntry,
)
from app.services.errors import (
    DuplicateTaskError,
    EmptyTaskTextError,
    InvalidTaskInputError,
    TaskNotFoundError,
    TaskRepositoryNotFoundError,
    TaskStateError,
)

_ALLOWED_CONTROL = {"\n", "\t"}


# --------------------------------------------------------------------------- #
# Normalization
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class NormalizedText:
    text: str
    truncated: bool
    original_bytes: int

    @property
    def stored_bytes(self) -> int:
        return len(self.text.encode("utf-8"))


def _strip_control_chars(value: str) -> str:
    out: list[str] = []
    for ch in value:
        if ch in _ALLOWED_CONTROL:
            out.append(ch)
            continue
        # Cc = control (incl. NUL, DEL, C1), Cf = format (zero-width chars, BOM,
        # bidi overrides). Both are dropped: they carry no meaning as issue text
        # and can break downstream framing.
        if unicodedata.category(ch) in ("Cc", "Cf"):
            continue
        out.append(ch)
    return "".join(out)


def normalize_text(raw: str, *, max_bytes: int) -> NormalizedText:
    """Deterministically clean untrusted issue text and cap its size.

    Injection strings ("ignore all previous instructions", fake ``SYSTEM:``
    prefixes, backticks, ...) are *not* special-cased -- they are preserved
    verbatim as inert data. They are neutralized structurally: the text only
    ever lands in a DB column, never in a prompt.
    """
    # original_bytes is the size of what was *submitted* -- provenance for a
    # later "was this truncated / trimmed?" question, independent of how much
    # normalization then removed.
    original_bytes = len(raw.encode("utf-8"))

    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = _strip_control_chars(text)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    # Collapse runs of blank lines to a single blank line (paragraph breaks are
    # kept; accidental double-spacing is not) and trim the whole blob.
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    text = text.strip()

    truncated = False
    if len(text.encode("utf-8")) > max_bytes:
        truncated = True
        # errors="ignore" drops a trailing partial multibyte sequence, keeping
        # the result on a valid UTF-8 character boundary.
        text = text.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore").rstrip()

    return NormalizedText(
        text=text, truncated=truncated, original_bytes=original_bytes
    )


def _first_line(text: str) -> str:
    for line in text.split("\n"):
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped
    return ""


def _clip_title(title: str, max_chars: int) -> str:
    title = title.strip()
    if len(title) > max_chars:
        title = title[: max_chars - 1].rstrip() + "…"
    return title


# --------------------------------------------------------------------------- #
# task_type inference
# --------------------------------------------------------------------------- #

_QUESTION_MARKERS = (
    "how do i",
    "how does",
    "how can i",
    "why does",
    "why is",
    "what is",
    "what does",
    "is it possible",
    "should i",
)
_REFACTOR_MARKERS = (
    "refactor",
    "clean up",
    "cleanup",
    "rename",
    "restructure",
    "reorganize",
    "tech debt",
    "technical debt",
    "simplify",
    "deduplicate",
    "extract method",
)
_BUG_MARKERS = (
    "bug",
    "fix",
    "broken",
    "incorrect",
    "wrong",
    "crash",
    "regression",
    "should not",
    "shouldn't",
    "instead of",
    "does not work",
    "doesn't work",
    "not working",
    "fails",
    "failure",
    "exception",
    "traceback",
    "unexpected",
)
_FEATURE_MARKERS = (
    "add ",
    "implement",
    "support for",
    "support ",
    "introduce",
    "new ",
    "allow ",
    "enable ",
    "provide ",
)


def infer_task_type(title: str, description: str) -> str:
    """Deterministic keyword classification. Precedence:
    QUESTION -> REFACTOR -> BUG -> FEATURE -> REQUIREMENT (default).
    """
    haystack = f"{title}\n{description}".lower()

    if title.strip().endswith("?") or any(m in haystack for m in _QUESTION_MARKERS):
        return TaskType.QUESTION.value
    if any(m in haystack for m in _REFACTOR_MARKERS):
        return TaskType.REFACTOR.value
    if any(m in haystack for m in _BUG_MARKERS):
        return TaskType.BUG.value
    if any(m in haystack for m in _FEATURE_MARKERS):
        return TaskType.FEATURE.value
    return TaskType.REQUIREMENT.value


# --------------------------------------------------------------------------- #
# Idempotency
# --------------------------------------------------------------------------- #


def compute_idempotency_key(repository_id: str, normalized_text: str) -> str:
    digest = hashlib.sha256()
    digest.update(repository_id.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(normalized_text.encode("utf-8"))
    return digest.hexdigest()


# --------------------------------------------------------------------------- #
# Schema mapping
# --------------------------------------------------------------------------- #


def _to_task_schema(row) -> TaskSchema:
    return TaskSchema(
        id=row.id,
        repository_id=row.repository_id,
        issue_id=row.issue_id,
        snapshot_id=row.snapshot_id,
        task_type=row.task_type,
        title=row.title,
        description=row.description_sanitized,
        constraints=row.constraints,
        priority=row.priority,
        allowed_paths=row.allowed_paths,
        idempotency_key=row.idempotency_key,
        state=row.state,
        terminal_reason=row.terminal_reason,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


# --------------------------------------------------------------------------- #
# Use cases
# --------------------------------------------------------------------------- #


def create_task(
    db: Session, *, settings: Settings, payload: TaskCreate
) -> TaskCreateResponse:
    repo = RepositoryRepository(db).get(payload.repository_id)
    if repo is None:
        raise TaskRepositoryNotFoundError(
            f"repository {payload.repository_id} not found"
        )

    if (payload.text is None) == (payload.issue is None):
        raise InvalidTaskInputError("provide exactly one of 'text' or 'issue'")

    if payload.text is not None:
        raw_body = payload.text
        issue_input = None
    else:
        assert payload.issue is not None  # narrowed by the check above
        raw_body = payload.issue.body
        issue_input = payload.issue

    norm = normalize_text(
        raw_body, max_bytes=settings.task_max_description_bytes
    )
    if not norm.text:
        raise EmptyTaskTextError("issue text is empty after normalization")

    raw_title = payload.title or (issue_input.title if issue_input else None)
    if not raw_title:
        raw_title = _first_line(norm.text)
    title = _clip_title(
        normalize_text(
            raw_title, max_bytes=settings.task_max_description_bytes
        ).text,
        settings.task_max_title_chars,
    )
    if not title:
        title = "Untitled task"

    task_type = payload.task_type or infer_task_type(title, norm.text)
    idempotency_key = compute_idempotency_key(repo.id, norm.text)

    existing = TaskRepository(db).get_by_idempotency_key(repo.id, idempotency_key)
    if existing is not None:
        raise DuplicateTaskError(
            "an identical task already exists for this repository",
            existing_task_id=existing.id,
        )

    issue_id = None
    if issue_input is not None:
        issue = IssueRepository(db).create(
            repository_id=repo.id,
            source=issue_input.source,
            title=title,
            body_sanitized=norm.text,
            external_ref=issue_input.external_ref,
        )
        issue_id = issue.id

    task = TaskRepository(db).create(
        repository_id=repo.id,
        task_type=task_type,
        title=title,
        description_sanitized=norm.text,
        idempotency_key=idempotency_key,
        issue_id=issue_id,
        constraints=payload.constraints,
        priority=payload.priority,
        allowed_paths=payload.allowed_paths,
        created_by=payload.created_by or "api",
    )
    TaskStepRepository(db).append(
        task_id=task.id, state=TaskState.PENDING.value, agent="ingest"
    )

    return TaskCreateResponse(
        task=_to_task_schema(task),
        normalization=NormalizationInfo(
            truncated=norm.truncated,
            original_bytes=norm.original_bytes,
            stored_bytes=norm.stored_bytes,
        ),
    )


def get_task(db: Session, task_id: str) -> TaskSchema:
    task = TaskRepository(db).get(task_id)
    if task is None:
        raise TaskNotFoundError(f"task {task_id} not found")
    return _to_task_schema(task)


def list_tasks(
    db: Session,
    *,
    repository_id: str | None = None,
    state: str | None = None,
    task_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> TaskList:
    repo = TaskRepository(db)
    rows = repo.list(
        repository_id=repository_id,
        state=state,
        task_type=task_type,
        limit=limit,
        offset=offset,
    )
    total = repo.count(
        repository_id=repository_id, state=state, task_type=task_type
    )
    return TaskList(
        items=[_to_task_schema(r) for r in rows],
        limit=limit,
        offset=offset,
        total=total,
    )


def run_task(db: Session, task_id: str) -> TaskSchema:
    tasks = TaskRepository(db)
    task = tasks.get(task_id)
    if task is None:
        raise TaskNotFoundError(f"task {task_id} not found")
    if task.state != TaskState.PENDING.value:
        raise TaskStateError(
            f"task {task_id} cannot be run from state {task.state}",
            current_state=task.state,
            attempted="run",
        )

    jobs = JobRepository(db)
    job = jobs.create(
        type=JobType.RUN_TASK.value,
        idempotency_key=f"run:{task.id}",
        task_id=task.id,
        dedupe_key=task.idempotency_key,
    )
    jobs.mark_queued(job.id)

    steps = TaskStepRepository(db)
    steps.close_current(task.id)
    tasks.set_state(task.id, TaskState.QUEUED.value)
    steps.append(
        task_id=task.id, state=TaskState.QUEUED.value, agent="orchestrator"
    )

    return _to_task_schema(tasks.get(task.id))


def cancel_task(
    db: Session, task_id: str, *, reason: str | None = None
) -> TaskSchema:
    tasks = TaskRepository(db)
    task = tasks.get(task_id)
    if task is None:
        raise TaskNotFoundError(f"task {task_id} not found")
    if task.state in TERMINAL_TASK_STATES:
        raise TaskStateError(
            f"task {task_id} is already in terminal state {task.state}",
            current_state=task.state,
            attempted="cancel",
        )

    jobs = JobRepository(db)
    for job in jobs.list_for_task(task.id):
        if job.state in (JobState.PENDING.value, JobState.QUEUED.value):
            jobs.mark_cancelled(job.id)

    steps = TaskStepRepository(db)
    steps.close_current(task.id)
    tasks.set_state(
        task.id,
        TaskState.CANCELLED.value,
        terminal_reason=reason or "cancelled via API",
    )
    steps.append(task_id=task.id, state=TaskState.CANCELLED.value, agent="api")

    return _to_task_schema(tasks.get(task.id))


def build_timeline(db: Session, task_id: str) -> TaskTimeline:
    task = TaskRepository(db).get(task_id)
    if task is None:
        raise TaskNotFoundError(f"task {task_id} not found")

    entries: list[TimelineEntry] = []

    for step in TaskStepRepository(db).list_for_task(task.id):
        entries.append(
            TimelineEntry(
                kind="STEP",
                seq=step.seq,
                state=step.state,
                at=step.entered_at,
                detail=step.agent,
            )
        )

    # The job's own creation is already represented by the task's PENDING step;
    # only its state-change events (each stamped with microsecond precision by
    # JobRepository, unlike the coarse DB-side created_at) are added here.
    for job in JobRepository(db).list_for_task(task.id):
        if job.queued_at is not None:
            entries.append(
                TimelineEntry(
                    kind="JOB", state="JOB_QUEUED", at=job.queued_at, detail=job.id
                )
            )
        if job.started_at is not None:
            entries.append(
                TimelineEntry(
                    kind="JOB",
                    state="JOB_RUNNING",
                    at=job.started_at,
                    detail=job.id,
                )
            )
        if job.finished_at is not None:
            entries.append(
                TimelineEntry(
                    kind="JOB",
                    state=f"JOB_{job.state}",
                    at=job.finished_at,
                    detail=job.id,
                )
            )

    # Tie-break equal timestamps deterministically: a STEP entry before a JOB
    # entry, then by step sequence.
    entries.sort(
        key=lambda e: (
            _as_utc(e.at),
            0 if e.kind == "STEP" else 1,
            e.seq if e.seq is not None else 0,
        )
    )
    return TaskTimeline(task_id=task.id, state=task.state, entries=entries)
