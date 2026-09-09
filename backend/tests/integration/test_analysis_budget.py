"""Phase 27 integration: the analysis wall-clock budget (Spec §37).

Over budget, the remaining files are marked SKIPPED with provenance, the
analysis row records a ``limit_reason``, and the pass returns partial results
instead of raising.
"""

from __future__ import annotations

import app.analysis.analyze as analyze_mod
from app.analysis.analyze import analyze_snapshot
from app.core.config import Settings
from app.ingestion.ingest import ingest_repository
from app.repository.analyses import AnalysisRepository
from app.repository.files import FileRepository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.schemas.repository import IngestRequest


def test_analysis_over_budget_degrades_to_partial(db_session, tmp_path, monkeypatch):
    repo_dir = tmp_path / "big-repo"
    repo_dir.mkdir()
    for i in range(5):
        (repo_dir / f"mod{i}.py").write_text(f"def f{i}():\n    return {i}\n")

    settings = Settings(
        ingestion_local_roots=[str(tmp_path)],
        artifacts_root=str(tmp_path / "artifacts"),
        _env_file=None,
    )

    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL", url_or_path=str(repo_dir), name="big-repo"
    )
    ingest_result = ingest_repository(
        db_session, repository=repo, request=IngestRequest(), settings=settings
    )
    snapshot = SnapshotRepository(db_session).get(ingest_result.snapshot_id)

    # monotonic(): 1st call sets `started`; the 2nd (first file's check) is
    # still in-budget; every call after that is way past the budget.
    ticks = iter([1000.0, 1000.0] + [1_000_000.0] * 50)
    monkeypatch.setattr(analyze_mod.time, "monotonic", lambda: next(ticks))

    result = analyze_snapshot(db_session, snapshot=snapshot, settings=settings)

    files = FileRepository(db_session).list_for_snapshot(snapshot.id)
    py = [f for f in files if f.path.endswith(".py")]
    skipped = [f for f in py if f.parse_status == "SKIPPED"]
    analysed = [f for f in py if f.parse_status == "OK"]

    assert skipped, "expected some files to be skipped once over budget"
    assert analysed, "expected at least one file analysed before the budget hit"

    row = AnalysisRepository(db_session).get_by_snapshot(snapshot.id)
    assert row.limit_reason is not None
    assert "budget" in row.limit_reason
    assert "analysis_incomplete" in (row.unknowns or [])
    assert row.summary["file_count"] < row.summary["files_total"]
    assert result.job_id is not None  # returned cleanly, no exception
