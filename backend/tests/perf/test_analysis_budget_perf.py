"""Phase 27 perf: a mid-size repository analyses well within the default
wall-clock budget (documents the headroom; not a hard CI gate)."""

from __future__ import annotations

import time

from app.analysis.analyze import analyze_snapshot
from app.core import limits
from app.core.config import Settings
from app.ingestion.ingest import ingest_repository
from app.repository.analyses import AnalysisRepository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.schemas.repository import IngestRequest

_N_FILES = 150
_N_FUNCS = 12


def test_midsize_repo_analysis_is_well_within_budget(db_session, tmp_path):
    repo_dir = tmp_path / "midsize"
    repo_dir.mkdir()
    for i in range(_N_FILES):
        body = "".join(
            f"def f{i}_{j}(x):\n    return x + {j}\n\n\n" for j in range(_N_FUNCS)
        )
        (repo_dir / f"mod_{i:03d}.py").write_text(body, encoding="utf-8")

    settings = Settings(
        ingestion_local_roots=[str(tmp_path)],
        artifacts_root=str(tmp_path / "artifacts"),
        _env_file=None,
    )
    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL", url_or_path=str(repo_dir), name="midsize"
    )
    ingest_result = ingest_repository(
        db_session, repository=repo, request=IngestRequest(), settings=settings
    )
    snapshot = SnapshotRepository(db_session).get(ingest_result.snapshot_id)

    t0 = time.monotonic()
    analyze_snapshot(db_session, snapshot=snapshot, settings=settings)
    elapsed = time.monotonic() - t0

    row = AnalysisRepository(db_session).get_by_snapshot(snapshot.id)
    assert row.limit_reason is None, "mid-size analysis should not hit the budget"
    assert row.summary["file_count"] == _N_FILES
    budget = limits.analysis_seconds(settings)
    assert elapsed < budget, f"{elapsed:.1f}s used of a {budget}s budget"
    # generous headroom expectation: this trivial tree parses in a fraction of it
    assert elapsed < max(30.0, budget / 4)
