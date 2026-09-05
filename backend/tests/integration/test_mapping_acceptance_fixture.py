"""Acceptance (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 15): the mapping for
"discount exceeds the configured maximum" returns the invoice module and
``calculate_total`` in the top-k, with evidence -- the plan's named golden,
tolerant of ordering.
"""

from __future__ import annotations

from app.analysis.analyze import analyze_snapshot
from app.ingestion.ingest import ingest_repository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.schemas.repository import IngestRequest
from app.services import mapping as mapping_service


def _prepare(db_session, ingestion_settings, acceptance_fixture_path):
    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL",
        url_or_path=str(acceptance_fixture_path),
        name="aegis-acceptance",
    )
    result = ingest_repository(
        db_session,
        repository=repo,
        request=IngestRequest(),
        settings=ingestion_settings,
    )
    snapshot = SnapshotRepository(db_session).get(result.snapshot_id)
    analyze_snapshot(db_session, snapshot=snapshot, settings=ingestion_settings)
    return snapshot.id


def test_discount_exceeds_maximum_maps_to_invoice(
    db_session, ingestion_settings, acceptance_fixture_path
):
    snapshot_id = _prepare(db_session, ingestion_settings, acceptance_fixture_path)

    mapping = mapping_service.run_mapping(
        db_session,
        settings=ingestion_settings,
        snapshot_id=snapshot_id,
        issue_text=(
            "Applying a discount above 50% still charges the full requested "
            "discount instead of capping it. The invoice total is wrong when "
            "the discount exceeds the configured maximum."
        ),
    )

    top_paths = [c.path for c in mapping.candidates]
    assert "invoice.py" in top_paths[: ingestion_settings.mapping_top_k]

    invoice = next(c for c in mapping.candidates if c.path == "invoice.py")
    assert "calculate_total" in invoice.symbols
    assert invoice.evidence
    assert any(e.kind in ("file", "symbol") for e in invoice.evidence)

    # stateless call: nothing persisted, task_id is None
    assert mapping.task_id is None
    assert mapping.overall_confidence > 0.0


def test_unrelated_issue_yields_low_confidence_or_unknown(
    db_session, ingestion_settings, acceptance_fixture_path
):
    snapshot_id = _prepare(db_session, ingestion_settings, acceptance_fixture_path)

    mapping = mapping_service.run_mapping(
        db_session,
        settings=ingestion_settings,
        snapshot_id=snapshot_id,
        issue_text="Upgrade the Kubernetes ingress controller to the latest chart.",
    )
    # nothing in this tiny fixture relates -> empty (UNKNOWN) or clearly weak
    if mapping.candidates:
        assert mapping.overall_confidence < 0.6
    else:
        assert mapping.overall_confidence == 0.0
