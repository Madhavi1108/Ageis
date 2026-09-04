"""Analyze the real test-repositories/aegis-acceptance fixture end to end.

See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 12 Acceptance test.
"""

from __future__ import annotations

from app.analysis.analyze import analyze_snapshot
from app.ingestion.ingest import ingest_repository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.schemas.repository import IngestRequest


def _ingest_acceptance(db_session, ingestion_settings, acceptance_fixture_path):
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


def test_analyze_acceptance_fixture(
    db_session, ingestion_settings, acceptance_fixture_path
):
    snapshot = _ingest_acceptance(
        db_session, ingestion_settings, acceptance_fixture_path
    )

    result = analyze_snapshot(
        db_session, snapshot=snapshot, settings=ingestion_settings
    )

    # invoice.py (module + calculate_total), utils.py (module + format_currency),
    # test_invoice.py (module + test_no_discount + test_discount_capped_at_50_percent).
    assert result.symbol_count == 7
    # test_invoice.py's `from invoice import calculate_total` is the only import.
    assert result.dependency_count == 1
    assert result.entry_points == []
    # No pytest.ini/conftest.py/pyproject.toml anywhere in this fixture -- test_*()
    # naming alone is not proof of pytest (confirmed design decision).
    assert result.test_framework is None
    assert result.package_manager is None
    assert result.build_backend is None
    assert "test_framework" in result.unknowns


def test_analyze_persists_local_import_edge(
    db_session, ingestion_settings, acceptance_fixture_path
):
    from app.repository.dependencies import DependencyRepository

    snapshot = _ingest_acceptance(
        db_session, ingestion_settings, acceptance_fixture_path
    )
    analyze_snapshot(db_session, snapshot=snapshot, settings=ingestion_settings)

    deps = DependencyRepository(db_session).list_for_snapshot(snapshot.id)
    assert len(deps) == 1
    assert deps[0].target == "invoice"
    assert deps[0].classification == "LOCAL"


def test_analyze_persists_symbols(
    db_session, ingestion_settings, acceptance_fixture_path
):
    from app.repository.symbols import SymbolRepository

    snapshot = _ingest_acceptance(
        db_session, ingestion_settings, acceptance_fixture_path
    )
    analyze_snapshot(db_session, snapshot=snapshot, settings=ingestion_settings)

    symbols = SymbolRepository(db_session).list_for_snapshot(snapshot.id)
    symbol_ids = {s.symbol_id for s in symbols}
    assert "invoice.py::calculate_total" in symbol_ids
    assert "utils.py::format_currency" in symbol_ids
