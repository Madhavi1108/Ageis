from __future__ import annotations

from app.core.config import Settings
from app.ingestion.ingest import ingest_repository
from app.repository.repositories import RepositoryRepository
from app.schemas.repository import IngestRequest


def test_oversized_file_yields_partially_supported(db_session, tmp_path):
    repo_dir = tmp_path / "big-repo"
    repo_dir.mkdir()
    (repo_dir / "small.py").write_text("x = 1\n")
    (repo_dir / "big.py").write_bytes(b"x" * 2_000)

    settings = Settings(
        ingestion_local_roots=[str(tmp_path)],
        ingestion_max_file_bytes=1_000,
        artifacts_root=str(tmp_path / "artifacts"),
        _env_file=None,
    )

    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL", url_or_path=str(repo_dir), name="big-repo"
    )

    result = ingest_repository(
        db_session, repository=repo, request=IngestRequest(), settings=settings
    )

    assert result.status == "PARTIALLY_SUPPORTED"
    assert result.limit_reason is not None
    assert "max_file_bytes" in result.limit_reason
    assert result.file_count == 2  # both rows kept, big.py marked SKIPPED
