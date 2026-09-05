"""Acceptance (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 16): a change to
invoice.py on the acceptance repo yields callers checkout.py / order_service.py,
test test_invoice.py, and a populated risk-signal bundle -- matching the
Specification's worked-example shape. Heuristic items are never FACT.
"""

from __future__ import annotations

from app.analysis.analyze import analyze_snapshot
from app.ingestion.ingest import ingest_repository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.schemas.repository import IngestRequest
from app.schemas.task import TaskCreate
from app.services import impact as impact_service
from app.services import mapping as mapping_service
from app.services import tasks as tasks_service


def _prepare(db_session, ingestion_settings, acceptance_fixture_path) -> str:
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

    task_md = (acceptance_fixture_path / "task.md").read_text(encoding="utf-8")
    created = tasks_service.create_task(
        db_session,
        settings=ingestion_settings,
        payload=TaskCreate(repository_id=repo.id, text=task_md),
    )
    task_id = created.task.id
    mapping_service.run_mapping(
        db_session, settings=ingestion_settings, task_id=task_id
    )
    return task_id


def test_impact_worked_example_shape(
    db_session, ingestion_settings, acceptance_fixture_path
):
    task_id = _prepare(db_session, ingestion_settings, acceptance_fixture_path)

    impact = impact_service.get_or_compute_impact(
        db_session, settings=ingestion_settings, task_id=task_id
    )

    assert "invoice.py" in impact.changed_set.files
    caller_refs = {c.ref for e in impact.callers for c in e.callers}
    assert {
        "checkout.py::process_checkout",
        "order_service.py::finalize_order",
    } <= caller_refs
    # direct callers are hop 1 and carry the real edge confidence
    for entry in impact.callers:
        for c in entry.callers:
            if c.hop == 1:
                assert c.edge_confidence in ("RESOLVED", "HEURISTIC", "UNRESOLVED")

    assert "test_invoice.py" in impact.related_tests
    assert impact.risk_signal_bundle["files_changed"].value is not None
    assert impact.report.splitlines()[0].startswith("Impact analysis for")


def test_heuristic_items_never_fact(
    db_session, ingestion_settings, acceptance_fixture_path
):
    task_id = _prepare(db_session, ingestion_settings, acceptance_fixture_path)
    impact = impact_service.get_or_compute_impact(
        db_session, settings=ingestion_settings, task_id=task_id
    )
    for item in [*impact.config_refs, *impact.db_refs]:
        assert item.basis == "INFERENCE"


def test_regression_areas_ranked_and_capped(
    db_session, ingestion_settings, acceptance_fixture_path
):
    task_id = _prepare(db_session, ingestion_settings, acceptance_fixture_path)
    impact = impact_service.get_or_compute_impact(
        db_session, settings=ingestion_settings, task_id=task_id
    )
    scores = [a.score for a in impact.regression_areas]
    assert scores == sorted(scores, reverse=True)
    assert (
        len(impact.regression_areas) <= ingestion_settings.impact_max_regression_areas
    )
