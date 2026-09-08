"""A hostile repository is fully contained during ingestion
(docs/SECURITY_MODEL.md Section 1/2): its git hooks never run, its ``.git`` is
stripped, no process is spawned, and a symlink pointing outside the tree does
not expose the target's content in the materialized workspace.
"""

from __future__ import annotations

import subprocess

from app.ingestion.ingest import ingest_repository
from app.ingestion.workspace import workspace_dir
from app.repository.repositories import RepositoryRepository
from app.schemas.repository import IngestRequest


def test_malicious_repo_is_contained(
    db_session, security_settings, malicious_repo, monkeypatch
):
    spawned: list = []
    real_popen = subprocess.Popen

    class SpyPopen(real_popen):
        def __init__(self, args, *a, **kw):
            spawned.append(args)
            super().__init__(args, *a, **kw)

    monkeypatch.setattr(subprocess, "Popen", SpyPopen)

    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL", url_or_path=str(malicious_repo), name="aegis-malicious"
    )
    ingested = ingest_repository(
        db_session,
        repository=repo,
        request=IngestRequest(),
        settings=security_settings,
    )

    # 1. nothing was executed from the hostile tree (no git hook, no test code)
    assert spawned == []
    assert not (malicious_repo.parent / "aegis_pwned").exists()

    # 2. the materialized workspace has no .git (so the pre-commit hook is gone)
    ws = workspace_dir(ingested.snapshot_id, security_settings)
    assert ws.is_dir()
    assert not (ws / ".git").exists()

    # 3. a symlink that pointed outside the tree does not leak the target's bytes
    leaked = list(ws.rglob("*"))
    for p in leaked:
        if p.is_file():
            assert "top secret" not in p.read_text(encoding="utf-8", errors="ignore")
