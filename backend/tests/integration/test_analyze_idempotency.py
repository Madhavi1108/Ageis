from __future__ import annotations

import time

from app.analysis.analyze import analyze_snapshot
from app.ingestion.ingest import ingest_repository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.repository.symbols import SymbolRepository
from app.schemas.repository import IngestRequest


def _ingest_and_get_snapshot(db_session, ingestion_settings, acceptance_fixture_path):
    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL",
        url_or_path=str(acceptance_fixture_path),
        name="aegis-acceptance",
    )
    ingest_result = ingest_repository(
        db_session,
        repository=repo,
        request=IngestRequest(),
        settings=ingestion_settings,
    )
    return SnapshotRepository(db_session).get(ingest_result.snapshot_id)


def test_reanalyzing_without_force_returns_cached_result(
    db_session, ingestion_settings, acceptance_fixture_path
):
    snapshot = _ingest_and_get_snapshot(
        db_session, ingestion_settings, acceptance_fixture_path
    )

    first = analyze_snapshot(db_session, snapshot=snapshot, settings=ingestion_settings)
    time.sleep(0.05)
    second = analyze_snapshot(
        db_session, snapshot=snapshot, settings=ingestion_settings
    )

    assert first.analysed_at == second.analysed_at


def test_force_reanalysis_replaces_symbols_not_duplicates(
    db_session, ingestion_settings, acceptance_fixture_path
):
    snapshot = _ingest_and_get_snapshot(
        db_session, ingestion_settings, acceptance_fixture_path
    )

    first = analyze_snapshot(db_session, snapshot=snapshot, settings=ingestion_settings)
    time.sleep(0.05)
    second = analyze_snapshot(
        db_session, snapshot=snapshot, settings=ingestion_settings, force=True
    )

    assert second.analysed_at != first.analysed_at
    symbols = SymbolRepository(db_session).list_for_snapshot(snapshot.id)
    assert len(symbols) == second.symbol_count == 7
