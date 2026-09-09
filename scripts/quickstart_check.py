#!/usr/bin/env python3
"""Non-Docker quickstart / documentation-accuracy gate (plan §36).

Drives the real ``backend/app`` pipeline end to end -- ingest -> analyze ->
plan -> implement -> test -> repair -> review -> score -> verify -> COMPLETED --
against ``test-repositories/aegis-acceptance`` with the deterministic
``MockProvider`` and the fake sandbox, in-process, no services to boot.

This is the same path the Phase 24 e2e suite checks
(``backend/tests/e2e/test_full_pipeline.py`` scenario A); it exists as a
single-command smoke test so ``README`` / ``docs/USER_GUIDE.md`` can be shown
to work in CI without Docker. The ``docker compose up`` variant is documented in
``README.md`` but is not CI-gated in this environment.

    python scripts/quickstart_check.py

Exit 0 + "QUICKSTART PASS" on success; non-zero otherwise.
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _REPO_ROOT / "backend"
for p in (str(_BACKEND), str(_REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

ACCEPTANCE_SRC = _REPO_ROOT / "test-repositories" / "aegis-acceptance"


def run() -> int:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.ai.provider import MockProvider
    from app.analysis.analyze import analyze_snapshot
    from app.core.config import Settings
    from app.ingestion.ingest import ingest_repository
    from app.models.base import Base
    from app.models.task import TaskState
    from app.orchestration import orchestrator
    from app.repository.repositories import RepositoryRepository
    from app.repository.snapshots import SnapshotRepository
    from app.schemas.repository import IngestRequest
    from app.schemas.task import TaskCreate
    from app.services import tasks as tasks_service
    from app.services import verification as verification_service

    from tests.e2e._acceptance_repo import build_acceptance_git_repo
    from tests.e2e._acceptance_scenarios import SCENARIO_ALLOWED_PATHS, register_scenario

    started = time.monotonic()
    tmp = Path(tempfile.mkdtemp(prefix="aegis_quickstart_"))
    work = tmp / "repo"
    build_acceptance_git_repo(work, source=ACCEPTANCE_SRC)

    settings = Settings(
        ingestion_local_roots=[str(work.parent)],
        artifacts_root=str(tmp / "artifacts"),
        sandbox_mode="fake",
        memory_enabled=True,
        orchestrator_open_pr=False,
        _env_file=None,
    )

    engine = create_engine(f"sqlite:///{tmp / 'quickstart.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()

    try:
        repo = RepositoryRepository(db).get_or_create(
            source_type="LOCAL", url_or_path=str(work), name=work.name
        )
        ingested = ingest_repository(
            db, repository=repo, request=IngestRequest(), settings=settings
        )
        assert ingested.status == "READY", ingested.status
        print(f"  ingested {ingested.commit_sha[:10]}  ({_lap(started)})")

        analyze_snapshot(
            db,
            snapshot=SnapshotRepository(db).get(ingested.snapshot_id),
            settings=settings,
        )
        print(f"  analyzed                    ({_lap(started)})")

        payload = TaskCreate(
            repository_id=repo.id,
            text=(ACCEPTANCE_SRC / "task.md").read_text(encoding="utf-8"),
            allowed_paths=SCENARIO_ALLOWED_PATHS["A"],
        )
        task_id = tasks_service.create_task(db, settings=settings, payload=payload).task.id

        provider = MockProvider()
        register_scenario(provider, "A", task_id)
        task = orchestrator.run_task(
            db, settings=settings, task_id=task_id, provider=provider
        )
        print(f"  pipeline -> {task.state:<20} ({_lap(started)})")

        if task.state == TaskState.AWAITING_APPROVAL.value:
            verification_service.resolve_decision(
                db,
                settings=settings,
                task_id=task_id,
                decision="APPROVE",
                reason="quickstart: fake sandbox validated the change",
                actor="quickstart@local",
            )
            from app.repository.tasks import TaskRepository

            task = TaskRepository(db).get(task_id)
            print(f"  approved -> {task.state:<20} ({_lap(started)})")

        if task.state != TaskState.COMPLETED.value:
            print(f"QUICKSTART FAIL: task ended in {task.state}, expected COMPLETED")
            return 1
    finally:
        db.close()

    print(f"QUICKSTART PASS  ({_lap(started)})")
    return 0


def _lap(started: float) -> str:
    return f"{time.monotonic() - started:5.1f}s"


if __name__ == "__main__":
    raise SystemExit(run())
