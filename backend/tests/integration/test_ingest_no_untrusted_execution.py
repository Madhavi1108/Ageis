"""Regression: ingesting a repository never spawns a process other than `git`
(invoked internally by GitPython), proving target-repository code is never executed.
"""

from __future__ import annotations

import subprocess

from app.ingestion.ingest import ingest_repository
from app.repository.repositories import RepositoryRepository
from app.schemas.repository import IngestRequest


def test_ingestion_spawns_only_git(
    db_session, ingestion_settings, acceptance_fixture_path, monkeypatch
):
    spawned: list[list[str]] = []
    real_popen = subprocess.Popen

    class SpyPopen(real_popen):
        def __init__(self, args, *a, **kw):
            spawned.append(args if isinstance(args, list) else [args])
            super().__init__(args, *a, **kw)

    monkeypatch.setattr(subprocess, "Popen", SpyPopen)

    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL",
        url_or_path=str(acceptance_fixture_path),
        name="aegis-acceptance",
    )
    ingest_repository(
        db_session,
        repository=repo,
        request=IngestRequest(),
        settings=ingestion_settings,
    )

    # test-repositories/aegis-acceptance has no .git, so open_local() returns None and
    # git isn't invoked at all here -- the assertion that matters is that *nothing*
    # (not git, not python, not anything from the fixture) was spawned.
    assert spawned == []
