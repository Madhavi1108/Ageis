"""Phase 27 perf: a short soak-shape check -- many GC cycles over churning
artifacts leave no leftover workspace directories and don't leak file
descriptors. This is a leak *shape* check, not a multi-hour soak (that belongs
in a nightly job).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.models.artifact import Artifact, ArtifactKind, ArtifactRetention
from app.models.base import Base
from app.models.task import Task, TaskState
from app.orchestration.gc import run_gc

_ITERATIONS = 60


def _fd_count() -> int | None:
    fd_dir = Path("/proc/self/fd")
    if sys.platform.startswith("linux") and fd_dir.is_dir():
        return len(list(fd_dir.iterdir()))
    return None


def _db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'soak.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


@pytest.mark.perf
def test_repeated_gc_over_churning_artifacts_does_not_leak(tmp_path):
    db = _db(tmp_path)
    settings = Settings(
        artifacts_root=str(tmp_path / "artifacts"),
        gc_ephemeral_grace_s=0,
        _env_file=None,
    )
    ws_root = tmp_path / "artifacts" / "workspaces"
    ws_root.mkdir(parents=True)

    fd_before = _fd_count()

    for n in range(_ITERATIONS):
        task = Task(
            repository_id="r1",
            task_type="BUG",
            title="t",
            description_sanitized="d",
            idempotency_key=f"soak-{n}",
            state=TaskState.COMPLETED.value,
        )
        db.add(task)
        db.commit()
        db.query(Task).filter(Task.id == task.id).update(
            {"updated_at": datetime.now(timezone.utc) - timedelta(hours=1)}
        )
        db.commit()

        wsdir = ws_root / f"ws-{n}"
        wsdir.mkdir()
        (wsdir / "blob.bin").write_bytes(b"x" * 4096)
        art = Artifact(
            store="FS",
            kind=ArtifactKind.WORKSPACE.value,
            uri=str(wsdir),
            retention=ArtifactRetention.EPHEMERAL.value,
            task_id=task.id,
        )
        db.add(art)
        db.commit()

        run_gc(db, settings)

    # every workspace was eligible (terminal task + zero grace) -> all reaped
    leftover = [p for p in ws_root.iterdir()]
    assert leftover == [], f"workspace dirs leaked: {leftover}"
    assert db.query(Artifact).count() == 0

    fd_after = _fd_count()
    if fd_before is not None and fd_after is not None:
        assert fd_after - fd_before <= 5, f"fd growth {fd_before} -> {fd_after}"

    db.close()
