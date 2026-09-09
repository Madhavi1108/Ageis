"""Phase 27 unit: artifact + workspace garbage collection (app/orchestration/gc.py)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.models.artifact import Artifact, ArtifactKind, ArtifactRetention
from app.models.base import Base
from app.models.task import Task, TaskState
from app.orchestration.gc import run_gc
from app.repository.artifacts import ArtifactRepository


def _db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _settings(tmp_path, **over) -> Settings:
    return Settings(
        artifacts_root=str(tmp_path / "artifacts"),
        gc_retained_days=over.pop("gc_retained_days", 90),
        gc_ephemeral_grace_s=over.pop("gc_ephemeral_grace_s", 3600),
        _env_file=None,
        **over,
    )


def _blob(tmp_path, name: str, body: bytes = b"x" * 10) -> str:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)
    return str(p)


def _add(db, **kw) -> Artifact:
    created_at = kw.pop("created_at", None)
    art = Artifact(store="FS", **kw)
    if created_at is not None:
        art.created_at = created_at
    db.add(art)
    db.commit()
    db.refresh(art)
    return art


def _task(db, state: str) -> Task:
    t = Task(
        repository_id="r1",
        task_type="BUG",
        title="t",
        description_sanitized="d",
        idempotency_key=f"k-{state}-{id(state)}",
        state=state,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def test_permanent_artifacts_are_never_collected(tmp_path):
    db = _db()
    uri = _blob(tmp_path, "trace.json")
    _add(
        db,
        kind=ArtifactKind.TRACE.value,
        uri=uri,
        retention=ArtifactRetention.PERMANENT.value,
        created_at=datetime.now(timezone.utc) - timedelta(days=10_000),
    )
    summary = run_gc(db, _settings(tmp_path))
    assert summary["artifacts_deleted"] == 0
    assert ArtifactRepository(db).list_by_retention(ArtifactRetention.PERMANENT.value)


def test_retained_artifact_expires_after_retention_window(tmp_path):
    db = _db()
    old = _add(
        db,
        kind=ArtifactKind.REPORT.value,
        uri=_blob(tmp_path, "old_report.json"),
        retention=ArtifactRetention.RETAINED.value,
        created_at=datetime.now(timezone.utc) - timedelta(days=91),
    )
    fresh = _add(
        db,
        kind=ArtifactKind.REPORT.value,
        uri=_blob(tmp_path, "fresh_report.json"),
        retention=ArtifactRetention.RETAINED.value,
        created_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    summary = run_gc(db, _settings(tmp_path, gc_retained_days=90))
    assert summary["artifacts_deleted"] == 1
    assert summary["bytes_freed"] >= 10
    assert db.get(Artifact, old.id) is None
    kept = db.get(Artifact, fresh.id)
    assert kept is not None and kept.expires_at is not None  # lazily backfilled


def test_ephemeral_workspace_collected_only_after_terminal_task_plus_grace(tmp_path):
    db = _db()
    running = _task(db, TaskState.IMPLEMENTING.value)
    done = _task(db, TaskState.COMPLETED.value)
    db.query(Task).filter(Task.id == done.id).update(
        {"updated_at": datetime.now(timezone.utc) - timedelta(hours=2)}
    )
    db.commit()

    live = _add(
        db,
        kind=ArtifactKind.WORKSPACE.value,
        uri=_blob(tmp_path, "artifacts/workspaces/live/f.txt"),
        retention=ArtifactRetention.EPHEMERAL.value,
        task_id=running.id,
    )
    dead = _add(
        db,
        kind=ArtifactKind.WORKSPACE.value,
        uri=_blob(tmp_path, "artifacts/workspaces/dead/f.txt"),
        retention=ArtifactRetention.EPHEMERAL.value,
        task_id=done.id,
    )
    summary = run_gc(db, _settings(tmp_path, gc_ephemeral_grace_s=3600))
    assert db.get(Artifact, dead.id) is None
    assert db.get(Artifact, live.id) is not None
    assert summary["artifacts_deleted"] == 1


def test_orphan_workspace_dir_with_no_artifact_row_is_reaped(tmp_path):
    db = _db()
    orphan = tmp_path / "artifacts" / "workspaces" / "orphan"
    orphan.mkdir(parents=True)
    (orphan / "junk.txt").write_bytes(b"y" * 50)
    import os

    old = (datetime.now(timezone.utc) - timedelta(hours=5)).timestamp()
    os.utime(orphan, (old, old))

    summary = run_gc(db, _settings(tmp_path, gc_ephemeral_grace_s=3600))
    assert not orphan.exists()
    assert summary["workspaces_reaped"] == 1


def test_recent_orphan_workspace_dir_is_left_alone(tmp_path):
    db = _db()
    recent = tmp_path / "artifacts" / "workspaces" / "recent"
    recent.mkdir(parents=True)
    (recent / "junk.txt").write_bytes(b"z" * 50)

    summary = run_gc(db, _settings(tmp_path, gc_ephemeral_grace_s=3600))
    assert recent.exists()
    assert summary["workspaces_reaped"] == 0
