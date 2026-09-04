from __future__ import annotations

from app.ingestion.ingest import ingest_repository
from app.repository.repositories import RepositoryRepository
from app.schemas.repository import IngestRequest


def test_reingesting_same_commit_returns_same_snapshot(
    db_session, ingestion_settings, acceptance_fixture_path
):
    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL",
        url_or_path=str(acceptance_fixture_path),
        name="aegis-acceptance",
    )

    first = ingest_repository(
        db_session,
        repository=repo,
        request=IngestRequest(),
        settings=ingestion_settings,
    )
    second = ingest_repository(
        db_session,
        repository=repo,
        request=IngestRequest(),
        settings=ingestion_settings,
    )

    assert first.snapshot_id == second.snapshot_id


def test_force_refreshes_existing_snapshot_in_place(
    db_session, ingestion_settings, acceptance_fixture_path
):
    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL",
        url_or_path=str(acceptance_fixture_path),
        name="aegis-acceptance",
    )

    first = ingest_repository(
        db_session,
        repository=repo,
        request=IngestRequest(),
        settings=ingestion_settings,
    )
    second = ingest_repository(
        db_session,
        repository=repo,
        request=IngestRequest(force=True),
        settings=ingestion_settings,
    )

    assert first.snapshot_id == second.snapshot_id
    assert second.status == "READY"
    assert second.file_count == first.file_count
