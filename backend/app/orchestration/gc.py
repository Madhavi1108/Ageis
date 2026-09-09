"""Artifact + workspace garbage collection (Phase 27, ADR-0009,
docs/DATA_MODEL.md §4, docs/SECURITY_MODEL.md §2 "leftover state").

``run_gc`` is invoked as a ``GC`` job (self-enqueued by the worker on
``settings.gc_interval_s``) and is also the ``python -m app.orchestration.gc``
entrypoint for external cron.

Policy:
  * PERMANENT artifacts (Trace / PR body / Benchmark) -- never collected.
  * RETAINED artifacts -- expire ``gc_retained_days`` after creation
    (``expires_at`` is lazily backfilled here from ``created_at``).
  * EPHEMERAL artifacts (WORKSPACE) -- collected once the owning task is
    terminal + ``gc_ephemeral_grace_s``; if there is no owning task, once
    ``created_at + gc_ephemeral_grace_s`` has passed.
  * ``<artifacts_root>/workspaces/<id>/`` directories with **no** artifact row
    pointing at them (a crashed ingest) and an old mtime -- reaped.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.models.artifact import ArtifactRetention
from app.models.task import TERMINAL_TASK_STATES
from app.repository.artifacts import ArtifactRepository
from app.repository.tasks import TaskRepository

_logger = logging.getLogger("app.orchestration.gc")


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _unlink(uri: str) -> int:
    """Remove a file or directory at ``uri``; return bytes freed (best effort)."""
    p = Path(uri)
    try:
        if p.is_dir():
            freed = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
            shutil.rmtree(p, ignore_errors=True)
            return freed
        if p.is_file():
            freed = p.stat().st_size
            p.unlink()
            return freed
    except OSError:
        pass
    return 0


def run_gc(db: Session, settings: Settings) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    artifacts = ArtifactRepository(db)
    tasks = TaskRepository(db)
    summary = {"artifacts_deleted": 0, "bytes_freed": 0, "workspaces_reaped": 0}

    # 1. lazily backfill expires_at for RETAINED artifacts
    retained_ttl = timedelta(days=settings.gc_retained_days)
    for art in artifacts.list_by_retention(ArtifactRetention.RETAINED.value):
        if art.expires_at is None:
            artifacts.set_expires_at(art.id, (_aware(art.created_at) or now) + retained_ttl)

    # 2. collect anything with an expires_at in the past
    for art in artifacts.list_expired(now):
        summary["bytes_freed"] += _unlink(art.uri)
        artifacts.delete(art.id)
        summary["artifacts_deleted"] += 1

    # 3. EPHEMERAL artifacts whose task is terminal + grace (or no task + grace)
    grace = timedelta(seconds=settings.gc_ephemeral_grace_s)
    live_workspace_uris: set[str] = set()
    for art in artifacts.list_by_retention(ArtifactRetention.EPHEMERAL.value):
        eligible_at: datetime | None = None
        if art.task_id:
            task = tasks.get(art.task_id)
            if task is not None and task.state in TERMINAL_TASK_STATES:
                eligible_at = (_aware(task.updated_at) or now) + grace
        else:
            eligible_at = (_aware(art.created_at) or now) + grace
        if eligible_at is not None and eligible_at <= now:
            summary["bytes_freed"] += _unlink(art.uri)
            artifacts.delete(art.id)
            summary["artifacts_deleted"] += 1
        else:
            live_workspace_uris.add(str(Path(art.uri).resolve()))

    # 4. sweep workspace dirs with no artifact row at all (crashed ingest)
    ws_root = Path(settings.artifacts_root) / "workspaces"
    if ws_root.is_dir():
        cutoff = now - grace
        for child in ws_root.iterdir():
            if not child.is_dir():
                continue
            if str(child.resolve()) in live_workspace_uris:
                continue
            try:
                mtime = datetime.fromtimestamp(child.stat().st_mtime, tz=timezone.utc)
            except OSError:
                continue
            if mtime <= cutoff:
                summary["bytes_freed"] += _unlink(str(child))
                summary["workspaces_reaped"] += 1

    return summary


def main() -> None:  # pragma: no cover -- CLI entrypoint (cron)
    from app.db.session import SessionLocal

    settings = get_settings()
    configure_logging(settings)
    db = SessionLocal()
    try:
        print(run_gc(db, settings))
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    main()
