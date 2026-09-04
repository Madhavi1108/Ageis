from __future__ import annotations

from app.analysis.analyze import analyze_snapshot
from app.ingestion.ingest import ingest_repository
from app.repository.files import FileRepository
from app.repository.repositories import RepositoryRepository
from app.schemas.repository import IngestRequest


def test_syntax_error_file_recorded_but_analysis_continues(db_session, tmp_path):
    from app.core.config import Settings
    from app.repository.snapshots import SnapshotRepository

    repo_dir = tmp_path / "broken-repo"
    repo_dir.mkdir()
    (repo_dir / "good.py").write_text("def ok():\n    return 1\n")
    (repo_dir / "bad.py").write_text("def broken(:\n    pass\n")

    settings = Settings(
        ingestion_local_roots=[str(tmp_path)],
        artifacts_root=str(tmp_path / "artifacts"),
        _env_file=None,
    )

    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL", url_or_path=str(repo_dir), name="broken-repo"
    )
    ingest_result = ingest_repository(
        db_session, repository=repo, request=IngestRequest(), settings=settings
    )
    snapshot = SnapshotRepository(db_session).get(ingest_result.snapshot_id)

    result = analyze_snapshot(db_session, snapshot=snapshot, settings=settings)

    files = {
        f.path: f for f in FileRepository(db_session).list_for_snapshot(snapshot.id)
    }
    assert files["bad.py"].parse_status == "SYNTAX_ERROR"
    assert files["bad.py"].parse_error is not None
    assert files["good.py"].parse_status == "OK"

    # good.py's symbols (module + ok) still get extracted despite bad.py failing to
    # parse (bad.py contributes zero symbols, not even a MODULE row, since the visitor
    # never runs on an unparseable file).
    assert result.symbol_count == 2
